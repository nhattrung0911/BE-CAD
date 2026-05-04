import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, engine
from app.main import app
from app.services.cache_service import cache
from fastapi.testclient import TestClient


def main() -> int:
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)
    checks = [
        ("health", "GET", "/health", None, 200),
        ("ready", "GET", "/ready", None, 200),
        ("variants", "GET", "/api/v1/products/hex-bolt-iso4014/variants", None, 200),
        ("geometry_variant", "GET", "/api/v1/geometry/variant/hex-bolt-iso4014-m8x30?lod=medium", None, 200),
    ]

    generated_hash_url = None
    for name, method, url, payload, expected in checks:
        response = client.request(method, url, json=payload)
        print(f"{name}: {response.status_code}")
        if response.status_code != expected:
            print(response.text)
            return 1
        if name == "geometry_variant":
            generated_hash_url = response.json()["hash_url"]

    if generated_hash_url is None:
        print("geometry_variant did not return hash_url")
        return 1

    hash_response = client.get(generated_hash_url)
    print(f"geometry_hash: {hash_response.status_code}")
    if hash_response.status_code != 200:
        print(hash_response.text)
        return 1
    if hash_response.headers.get("cache-control") != "public, max-age=31536000, immutable":
        print("geometry_hash missing immutable cache header")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
