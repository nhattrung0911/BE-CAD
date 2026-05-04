from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.repositories.artifacts import ArtifactRepository
from app.repositories.jobs import JobRepository
from app.cad.template_base import GeneratedModel
from app.services.cache_service import cache
from app.services.jobs import QUEUE_PREVIEW_FAST, enqueue_generation_job
from app.workers.tasks import run_generation_job


client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    settings.model_sync_generation = True
    settings.cad_backend = "mock"


def test_production_resolve_creates_pending_model_job():
    settings.model_sync_generation = False

    response = client.post(
        "/api/v1/models/resolve",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 6, "L": 30, "P": 1, "k": 4, "s": 10, "b": 18},
            "format": "glb",
            "quality": "preview",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["source"] == "queued_parametric"

    job_response = client.get(f"/api/v1/model-jobs/{body['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["job_id"] == body["job_id"]
    assert job["status"] == "pending"
    assert job["artifact"] is None


def test_sync_dev_mode_still_generates_preview_inline():
    response = client.post(
        "/api/v1/models/resolve",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 6, "L": 30, "P": 1, "k": 4, "s": 10, "b": 18},
            "format": "glb",
            "quality": "preview",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["source"] == "generated_parametric"
    assert body["artifact"]["url"].endswith("preview.glb")


def test_sync_preview_inline_allows_cadquery_backend(monkeypatch):
    settings.cad_backend = "cadquery"

    class FakeCadQueryBackend:
        def generate(self, product_id, params, fmt, quality):
            return GeneratedModel(
                content=b"glTF\x02\x00\x00\x00fake-cadquery-glb",
                format=fmt,
                metadata={"generator": "cadquery", "exporter": "cadquery_assembly_glb"},
            )

    monkeypatch.setattr("app.services.model_resolver.get_cad_backend", lambda name: FakeCadQueryBackend())

    response = client.post(
        "/api/v1/models/resolve",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
            "format": "glb",
            "quality": "preview",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["source"] == "generated_parametric"


def test_worker_marks_job_done_and_persists_artifact():
    queued = enqueue_generation_job(
        queue_name=QUEUE_PREVIEW_FAST,
        product_id="washer-iso7089",
        params={"OD": 12, "ID": 6, "h": 1.6},
        fmt="glb",
        quality="preview",
        template_version=settings.template_version,
    )

    result = run_generation_job(queued.job_id)

    assert result["status"] == "done"
    job_response = client.get(f"/api/v1/model-jobs/{queued.job_id}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "done"
    assert job["artifact"]["format"] == "glb"
    assert job["artifact"]["url"].endswith("preview.glb")

    with SessionLocal() as session:
        persisted = JobRepository(session).find_by_job_id(queued.job_id)
        artifact = ArtifactRepository(session).find_resolved_model(
            product_id=persisted.product_id,
            params_hash=persisted.params_hash,
            fmt=persisted.format,
            quality=persisted.quality,
        )
    assert persisted.result_artifact_id == artifact.id


def test_worker_sets_running_before_generation(monkeypatch):
    queued = enqueue_generation_job(
        queue_name=QUEUE_PREVIEW_FAST,
        product_id="washer-iso7089",
        params={"OD": 12, "ID": 6, "h": 1.6},
        fmt="glb",
        quality="preview",
        template_version=settings.template_version,
    )

    class ObservingBackend:
        def generate(self, product_id, params, fmt, quality):
            with SessionLocal() as session:
                job = JobRepository(session).find_by_job_id(queued.job_id)
                observed_status = job.status
            assert observed_status == "running"
            return GeneratedModel(content=b'{"generator":"fake"}', format=fmt, metadata={"generator": "fake"})

    monkeypatch.setattr("app.services.job_runner.get_cad_backend", lambda name: ObservingBackend())

    result = run_generation_job(queued.job_id)

    assert result["status"] == "done"


def test_worker_marks_job_failed_when_generation_fails():
    queued = enqueue_generation_job(
        queue_name=QUEUE_PREVIEW_FAST,
        product_id="washer-iso7089",
        params={"OD": 12, "h": 1.6},
        fmt="glb",
        quality="preview",
        template_version=settings.template_version,
    )

    result = run_generation_job(queued.job_id)

    assert result["status"] == "failed"
    job_response = client.get(f"/api/v1/model-jobs/{queued.job_id}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "failed"
    assert "Missing required params" in job["error_message"]
    assert job["artifact"] is None
