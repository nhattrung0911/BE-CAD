from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.db.models import GeometryCacheMetrics
from app.main import app
from app.repositories.geometry_metrics import GeometryCacheMetricsRepository
from app.services.cache_service import cache


client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_geometry_metrics_repository_tracks_access_count_and_top_skus():
    with SessionLocal() as session:
        repo = GeometryCacheMetricsRepository(session)
        repo.upsert(params_hash="hash-a", product_id="hex-bolt-iso4014", lod="medium", file_size_bytes=100)
        repo.upsert(params_hash="hash-a", product_id="hex-bolt-iso4014", lod="medium", file_size_bytes=120)
        repo.upsert(params_hash="hash-b", product_id="washer-iso7089", lod="low", file_size_bytes=80)
        session.commit()
        top = repo.top_skus(limit=2)

    assert top[0].params_hash == "hash-a"
    assert top[0].access_count == 2
    assert top[0].file_size_bytes == 120
    assert top[1].params_hash == "hash-b"


def test_geometry_variant_request_persists_cache_metrics_row():
    response = client.get("/api/v1/geometry/variant/hex-bolt-iso4014-m8x30?lod=medium")

    assert response.status_code == 200
    body = response.json()

    with SessionLocal() as session:
        metric = session.get(GeometryCacheMetrics, body["hash"])

    assert metric is not None
    assert metric.product_id == "hex-bolt-iso4014"
    assert metric.lod == "medium"
    assert metric.access_count == 1
    assert metric.file_size_bytes == body["artifact"]["file_size"]


def test_geometry_variant_request_increments_existing_metrics_row():
    first = client.get("/api/v1/geometry/variant/hex-bolt-iso4014-m8x30?lod=medium")
    second = client.get("/api/v1/geometry/variant/hex-bolt-iso4014-m8x30?lod=medium")

    assert first.status_code == 200
    assert second.status_code == 200

    params_hash = second.json()["hash"]
    with SessionLocal() as session:
        metric = session.get(GeometryCacheMetrics, params_hash)

    assert metric is not None
    assert metric.access_count == 2
