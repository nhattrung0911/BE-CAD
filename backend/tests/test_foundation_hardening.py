from fastapi.testclient import TestClient
from pathlib import Path

from app.core.config import settings
from app.core.database import Base, engine, should_auto_create_schema
from app.main import app
from app.services.cache_service import cache
from app.services.storage import LocalStorage


client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    settings.environment = "local"
    settings.admin_api_key = None
    settings.auto_create_schema = True
    settings.require_redis_for_ready = False
    settings.max_upload_bytes = 100 * 1024 * 1024


def test_vendor_asset_upload_requires_admin_api_key_when_configured():
    settings.admin_api_key = "test-admin-key"

    response = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("bolt.glb", b"glb-data", "model/gltf-binary")},
    )

    assert response.status_code == 401


def test_vendor_asset_upload_accepts_valid_admin_api_key():
    settings.admin_api_key = "test-admin-key"

    response = client.post(
        "/api/v1/vendor-assets",
        headers={"X-Admin-API-Key": "test-admin-key"},
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("bolt.glb", b"glb-data", "model/gltf-binary")},
    )

    assert response.status_code == 201
    assert response.json()["storage_key"] == "hex-bolt-iso4014/glb/bolt.glb"


def test_vendor_asset_upload_rejects_invalid_format_and_status_values():
    response = client.post(
        "/api/v1/vendor-assets",
        data={
            "product_id": "hex-bolt-iso4014",
            "format": "exe",
            "license_status": "unknown",
            "validation_status": "maybe",
        },
        files={"file": ("bolt.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["format"] == "unsupported"


def test_vendor_asset_upload_rejects_files_over_configured_limit():
    settings.max_upload_bytes = 4

    response = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("bolt.glb", b"too-large", "model/gltf-binary")},
    )

    assert response.status_code == 413


def test_local_storage_rejects_path_traversal_keys():
    storage = LocalStorage(Path("storage/key-safety-test"), "/files")

    try:
        storage.put_bytes("../escape.glb", b"bad")
    except ValueError as exc:
        assert "Unsafe storage key" in str(exc)
    else:
        raise AssertionError("Expected unsafe storage key to be rejected")


def test_model_resolve_rejects_unknown_product_before_generation():
    response = client.post(
        "/api/v1/models/resolve",
        json={"product_id": "unknown-product", "params": {}, "format": "glb", "quality": "preview"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_model_resolve_rejects_missing_required_parameters():
    response = client.post(
        "/api/v1/models/resolve",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 8, "L": 30},
            "format": "glb",
            "quality": "preview",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["missing"] == ["P", "k", "s", "b"]


def test_production_environment_does_not_auto_create_schema():
    settings.environment = "production"
    settings.auto_create_schema = True

    assert should_auto_create_schema() is False


def test_metrics_reflect_real_request_count():
    before = client.get("/metrics").json()["cad_platform_requests_total"]

    client.get("/health")

    after = client.get("/metrics").json()["cad_platform_requests_total"]
    assert after >= before + 1


def test_ready_fails_when_redis_is_required_but_unavailable():
    original_require_redis = settings.require_redis_for_ready
    original_redis_url = settings.redis_url
    settings.require_redis_for_ready = True
    settings.redis_url = None

    try:
        response = client.get("/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["redis"] == "missing"
    finally:
        settings.require_redis_for_ready = original_require_redis
        settings.redis_url = original_redis_url
