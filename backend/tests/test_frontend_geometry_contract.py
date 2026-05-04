from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.services.cache_service import cache


client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_product_variants_are_grouped_for_size_picker():
    response = client.get("/api/v1/products/hex-bolt-iso4014/variants")

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "hex-bolt-iso4014"
    assert body["total"] >= 3
    assert "M8" in body["grouped_by_diameter"]

    variant = body["grouped_by_diameter"]["M8"][0]
    assert variant["variant_id"] == "hex-bolt-iso4014-m8x30"
    assert variant["params"] == {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22}
    assert variant["geometry"]["low_hash"]
    assert variant["geometry"]["medium_hash"]
    assert variant["geometry"]["high_hash"]


def test_geometry_variant_resolves_ready_artifact_for_threejs_viewer():
    response = client.get("/api/v1/geometry/variant/hex-bolt-iso4014-m8x30?lod=medium")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["variant_id"] == "hex-bolt-iso4014-m8x30"
    assert body["lod"] == "medium"
    assert body["source"] == "generated_parametric"
    assert body["artifact"]["format"] == "glb"
    assert body["artifact"]["url"].endswith("/preview.glb")
    assert body["params"]["d"] == 8


def test_geometry_generate_returns_stable_hash_and_immutable_hash_url():
    response = client.post(
        "/api/v1/geometry/generate",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 10, "L": 40, "P": 1.5, "k": 6.4, "s": 17, "b": 26},
            "lod": "high",
            "format": "glb",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["hash"]
    assert body["hash_url"] == f"/api/v1/geometry/hash/{body['hash']}"

    hash_response = client.get(body["hash_url"])
    assert hash_response.status_code == 200
    assert hash_response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert hash_response.content
