from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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
