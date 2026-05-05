from fastapi.testclient import TestClient
from app.core.database import Base, engine
from app.main import app
from app.services.cache_service import cache

client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_resolve_hex_bolt():
    r = client.post("/api/v1/models/resolve", json={
        "product_id": "hex-bolt-iso4014",
        "params": {"d": 6, "L": 30, "P": 1, "k": 4, "s": 10, "b": 18},
        "format": "glb",
        "quality": "preview"
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["artifact"]["url"].endswith("preview.glb")
    assert [annotation["key"] for annotation in body["annotations"]] == ["d", "L", "k", "s", "b"]
