from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.services.cache_service import cache


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
