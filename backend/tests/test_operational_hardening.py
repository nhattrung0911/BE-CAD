from fastapi.testclient import TestClient
from pathlib import Path
import sys
from types import SimpleNamespace

from app.core.database import Base, engine
from app.core.config import settings
from app.main import app
from app.services.cache_service import cache
from app.services.storage import S3Storage


client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_ready_checks_database_and_storage_backends():
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "artifact_storage": "ok",
            "raw_asset_storage": "ok",
            "catalog": "ok",
        },
    }


def test_geometry_generate_rejects_unknown_product():
    response = client.post(
        "/api/v1/geometry/generate",
        json={
            "product_id": "unknown-product",
            "params": {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_geometry_generate_rejects_missing_required_parameters():
    response = client.post(
        "/api/v1/geometry/generate",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 8, "L": 30},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "Invalid product parameters"
    assert body["detail"]["missing"] == ["P", "k", "s", "b"]


def test_production_env_template_satisfies_compose_contract():
    repo_root = Path(__file__).resolve().parents[2]
    env_text = (repo_root / "infra" / ".env.production.example").read_text()
    compose_text = (repo_root / "infra" / "docker-compose.yml").read_text()

    required_keys = {
        "APP_ENV_FILE",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
        "S3_PUBLIC_BASE_URL",
    }
    env_keys = {
        line.split("=", 1)[0]
        for line in env_text.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert required_keys.issubset(env_keys)
    assert "${APP_ENV_FILE:-.env.example}" in compose_text
    assert "redis-server --requirepass" in compose_text


def test_s3_storage_uses_public_base_url_for_artifact_urls(monkeypatch):
    class FakeS3Client:
        def put_object(self, **kwargs):
            return None

    fake_boto3 = SimpleNamespace(client=lambda service: FakeS3Client())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    original_base_url = getattr(settings, "s3_public_base_url", None)
    settings.s3_public_base_url = "https://cdn.example.test/cad-assets"

    try:
        storage = S3Storage("bucket", "/artifacts")
        stored = storage.put_bytes("product/hash/preview.glb", b"glTF", content_type="model/gltf-binary")

        assert stored["url"] == "https://cdn.example.test/cad-assets/product/hash/preview.glb"
    finally:
        settings.s3_public_base_url = original_base_url
