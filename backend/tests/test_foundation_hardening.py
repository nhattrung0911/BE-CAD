from fastapi.testclient import TestClient
from pathlib import Path
import logging
import time

from app.core.config import Settings, settings
from app.core.database import Base, engine, should_auto_create_schema
from app.main import app
from app.services.cache_service import InMemoryCache, cache
from app.services.product_service import ProductService
from app.services.storage import LocalStorage
from app.workers.tasks import dispatch_generation_job, get_celery_app


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


def test_production_settings_reject_mock_backend():
    try:
        Settings(
            environment="production",
            cad_backend="mock",
            auto_create_schema=False,
            require_redis_for_ready=True,
        )
    except ValueError as exc:
        assert "CAD_BACKEND=mock" in str(exc)
    else:
        raise AssertionError("Expected production settings to reject mock backend")


def test_production_settings_reject_auto_create_schema():
    try:
        Settings(
            environment="production",
            cad_backend="cadquery",
            auto_create_schema=True,
            require_redis_for_ready=True,
        )
    except ValueError as exc:
        assert "AUTO_CREATE_SCHEMA=true" in str(exc)
    else:
        raise AssertionError("Expected production settings to reject auto schema creation")


def test_production_settings_require_redis_ready_flag():
    try:
        Settings(
            environment="production",
            cad_backend="cadquery",
            auto_create_schema=False,
            require_redis_for_ready=False,
        )
    except ValueError as exc:
        assert "REQUIRE_REDIS_FOR_READY" in str(exc)
    else:
        raise AssertionError("Expected production settings to require Redis readiness")


def test_metrics_reflect_real_request_count():
    before_text = client.get("/metrics").text
    before = _prometheus_metric_value(before_text, "cad_platform_requests_total")

    client.get("/health")

    after_text = client.get("/metrics").text
    after = _prometheus_metric_value(after_text, "cad_platform_requests_total")
    assert after >= before + 1


def test_metrics_prometheus_format():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP cad_platform_requests_total" in response.text
    assert "# TYPE cad_platform_requests_total counter" in response.text
    assert "# HELP cad_platform_cache_hits_total" in response.text
    assert "# HELP cad_platform_cache_misses_total" in response.text


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


def test_in_memory_cache_expires_entries():
    cache_impl = InMemoryCache()
    cache_impl.set("k", "v", ttl_seconds=1)
    assert cache_impl.get("k") == "v"
    time.sleep(1.1)
    assert cache_impl.get("k") is None


def test_in_memory_cache_no_ttl_does_not_expire():
    cache_impl = InMemoryCache()
    cache_impl.set("k", "v", ttl_seconds=None)
    assert cache_impl.get("k") == "v"


def test_expired_key_removed_from_dict():
    cache_impl = InMemoryCache()
    cache_impl.set("k", "v", ttl_seconds=1)
    time.sleep(1.1)
    cache_impl.get("k")
    assert "k" not in cache_impl._data


def test_dispatch_without_redis_logs_warning_not_raises(caplog):
    original_redis_url = settings.redis_url
    settings.redis_url = None
    try:
        with caplog.at_level(logging.WARNING):
            dispatch_generation_job("preview_fast", "test-job-123")
        assert "No REDIS_URL" in caplog.text
    finally:
        settings.redis_url = original_redis_url


def test_get_celery_app_raises_without_redis():
    original_redis_url = settings.redis_url
    settings.redis_url = None
    try:
        try:
            get_celery_app()
        except RuntimeError as exc:
            assert "REDIS_URL is required" in str(exc)
        else:
            raise AssertionError("Expected get_celery_app to require Redis")
    finally:
        settings.redis_url = original_redis_url


def test_ingest_2d_requires_admin_key_when_configured():
    settings.admin_api_key = "test-admin-key"

    response = client.post(
        "/api/v1/ingest/2d",
        json={"product_id": "hex-bolt-iso4014", "content": "M8 d:8.0 L:30"},
    )

    assert response.status_code == 401


def test_ingest_2d_accepts_valid_admin_key():
    settings.admin_api_key = "test-admin-key"

    response = client.post(
        "/api/v1/ingest/2d",
        headers={"X-Admin-API-Key": "test-admin-key"},
        json={"product_id": "hex-bolt-iso4014", "content": "M8 d:8.0 L:30"},
    )

    assert response.status_code == 200


def test_product_service_variant_lookup_is_cached(monkeypatch):
    service = ProductService()
    call_count = {"count": 0}
    original = ProductService.list_variants

    def counting_list_variants(self, product_id):
        call_count["count"] += 1
        return original(self, product_id)

    monkeypatch.setattr(ProductService, "list_variants", counting_list_variants)

    first = service.get_variant("hex-bolt-iso4014-m8x30")
    second = service.get_variant("hex-bolt-iso4014-m8x30")

    assert first.variant_id == second.variant_id == "hex-bolt-iso4014-m8x30"
    assert call_count["count"] <= len(service.list_products())


def _prometheus_metric_value(payload: str, metric_name: str) -> int:
    for line in payload.splitlines():
        if line.startswith(f"{metric_name} "):
            return int(float(line.split(" ", 1)[1]))
    raise AssertionError(f"Metric not found: {metric_name}")
