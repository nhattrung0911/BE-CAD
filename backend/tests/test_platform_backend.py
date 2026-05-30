import io
import hashlib

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.db.models import Artifact
from app.main import app
from app.repositories.artifacts import ArtifactRepository
from app.repositories.vendor_assets import VendorAssetRepository
from app.services.artifact_service import ArtifactService, artifact_service
from app.services.cache_service import cache
from app.services.jobs import QUEUE_BATCH_PREGENERATE, QUEUE_PREVIEW_FAST, enqueue_generation_job


client = TestClient(app)


def setup_function():
    cache.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_artifact_repository_persists_artifact_metadata():
    with SessionLocal() as session:
        repo = ArtifactRepository(session)
        artifact = repo.create(
            product_id="washer-iso7089",
            artifact_type="parametric",
            format="glb",
            quality="preview",
            storage_key="washer/key/preview.glb",
            sha256="abc123",
            file_size=12,
            source="generated_parametric",
            params_hash="hash1",
        )
        session.commit()

        found = repo.find_by_storage_key("washer/key/preview.glb")

    assert found is not None
    assert artifact.id == found.id
    assert found.product_id == "washer-iso7089"
    assert found.source == "generated_parametric"


def test_vendor_asset_registration_stores_checksum_and_license_state():
    payload = b"solid vendor step bytes"
    response = client.post(
        "/api/v1/vendor-assets",
        data={
            "product_id": "hex-bolt-iso4014",
            "format": "step",
            "license_status": "approved",
            "validation_status": "valid",
        },
        files={"file": ("bolt.step", io.BytesIO(payload), "application/step")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["product_id"] == "hex-bolt-iso4014"
    assert body["format"] == "step"
    assert body["license_status"] == "approved"
    assert body["validation_status"] == "valid"
    assert body["sha256"]
    assert body["storage_key"].endswith("/bolt.step")

    # Resolver gating requires both approved license AND valid (admin-reviewed)
    # validation. The repository helpers used by the resolver enforce that
    # contract, so unreviewed (pending) files are intentionally invisible.
    with SessionLocal() as session:
        found = VendorAssetRepository(session).find_exact(
            product_id="hex-bolt-iso4014",
            fmt="step",
        )
    assert found is not None
    assert found.sha256 == body["sha256"]


def test_resolver_prefers_registered_vendor_asset_for_exact_format():
    client.post(
        "/api/v1/vendor-assets",
        data={
            "product_id": "hex-bolt-iso4014",
            "format": "glb",
            "license_status": "approved",
            "validation_status": "valid",
        },
        files={"file": ("bolt.glb", io.BytesIO(b"vendor glb"), "model/gltf-binary")},
    )

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
    assert body["source"] == "vendor_exact"
    assert body["artifact"]["url"].endswith("bolt.glb")


def test_engineering_generation_is_queued_when_no_cached_or_vendor_asset():
    from app.workers import tasks as worker_tasks

    original_redis = settings.redis_url
    original_ensure = worker_tasks.ensure_async_dispatch_available
    original_dispatch = worker_tasks.dispatch_generation_job
    settings.redis_url = "redis://fake"
    worker_tasks.ensure_async_dispatch_available = lambda: None
    worker_tasks.dispatch_generation_job = lambda queue_name, job_id: None

    try:
        response = client.post(
            "/api/v1/models/resolve",
            json={
                "product_id": "hex-bolt-iso4014",
                "params": {"d": 8, "L": 40, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
                "format": "step",
                "quality": "engineering",
            },
        )
    finally:
        settings.redis_url = original_redis
        worker_tasks.ensure_async_dispatch_available = original_ensure
        worker_tasks.dispatch_generation_job = original_dispatch

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["source"] == "queued_parametric"
    assert body["job_id"].startswith("job_")


def test_resolver_regenerates_stale_mock_artifact_when_backend_is_cadquery(monkeypatch):
    from app.cad.template_base import GeneratedModel
    from app.services.hash_service import stable_params_hash
    from app.services.job_runner import model_artifact_key

    params = {"d": 12, "s": 18, "m": 18, "lod": "medium"}
    params_hash = stable_params_hash(
        "hex-nut-din6330",
        settings.template_version,
        "preview",
        "glb",
        params,
    )
    storage_key = model_artifact_key("hex-nut-din6330", params_hash, "preview", "glb")
    stale_payload = b'{\n  "format": "glb",\n  "generator": "mock"\n}'

    stored = artifact_service.put_bytes(storage_key, stale_payload, content_type="model/gltf-binary")
    with SessionLocal() as session:
        ArtifactRepository(session).create(
            product_id="hex-nut-din6330",
            artifact_type="model",
            format="glb",
            quality="preview",
            storage_key=stored["storage_key"],
            sha256=stored["sha256"],
            file_size=stored["file_size"],
            source="generated_parametric",
            params_hash=params_hash,
            metadata={"generator": "mock", "template": "hex_nut"},
        )
        session.commit()

    class FakeCadQueryBackend:
        def generate(self, product_id, generated_params, fmt, quality):
            assert product_id == "hex-nut-din6330"
            assert generated_params == params
            assert fmt == "glb"
            assert quality == "preview"
            return GeneratedModel(
                content=b"glTF\x02\x00\x00\x00real-binary-gltf",
                format="glb",
                metadata={"generator": "cadquery", "template": "hex_nut", "exporter": "cadquery_assembly_glb"},
            )

    original_backend = settings.cad_backend
    settings.cad_backend = "cadquery"
    monkeypatch.setattr("app.services.model_resolver.get_cad_backend", lambda name: FakeCadQueryBackend())
    monkeypatch.setattr("app.services.job_runner.get_cad_backend", lambda name: FakeCadQueryBackend())

    try:
        response = client.post(
            "/api/v1/models/resolve",
            json={
                "product_id": "hex-nut-din6330",
                "params": params,
                "format": "glb",
                "quality": "preview",
            },
        )
    finally:
        settings.cad_backend = original_backend

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["source"] == "generated_parametric"

    artifact_bytes = artifact_service.read_bytes(storage_key)
    assert artifact_bytes.startswith(b"glTF")
    assert hashlib.sha256(artifact_bytes).hexdigest() == body["artifact"]["sha256"]


def test_enqueue_generation_job_uses_named_queues():
    preview = enqueue_generation_job(
        queue_name=QUEUE_PREVIEW_FAST,
        product_id="washer-iso7089",
        params={"OD": 12, "ID": 6, "h": 1.6},
        fmt="glb",
        quality="preview",
    )
    batch = enqueue_generation_job(
        queue_name=QUEUE_BATCH_PREGENERATE,
        product_id="washer-iso7089",
        params={"OD": 12, "ID": 6, "h": 1.6},
        fmt="glb",
        quality="preview",
    )

    assert preview.queue_name == "preview_fast"
    assert batch.queue_name == "batch_pregenerate"
    assert preview.status == "pending"


def test_2d_ingestion_extracts_dimensions_and_metadata():
    html = """
    <svg><text>h:6.8-7.2</text><text>d1:12.8-13.2</text><text>OD:99.8-100.2</text></svg>
    <table>
      <tr><td>unit</td><td>mm</td></tr>
      <tr><td>material</td><td>65Mn</td></tr>
      <tr><td>standard</td><td>GB891</td></tr>
      <tr><td>size</td><td>100</td></tr>
      <tr><td>name</td><td>Retaining ring</td></tr>
      <tr><td>surface</td><td>phosphate</td></tr>
      <tr><td>barcode</td><td>6901234567890</td></tr>
    </table>
    """

    response = client.post(
        "/api/v1/ingest/2d",
        json={"product_id": "retaining-ring-gb891", "content": html},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dimensions"]["h"]["min"] == 6.8
    assert body["dimensions"]["OD"]["max"] == 100.2
    assert body["metadata"]["unit"] == "mm"
    assert body["metadata"]["material"] == "65Mn"
    assert body["metadata"]["barcode"] == "6901234567890"


def test_put_generated_model_reuses_existing_artifact_without_rewriting_storage():
    class FakeStorage:
        def __init__(self) -> None:
            self.write_calls = 0
            self.objects = {}

        def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> dict:
            import hashlib

            self.write_calls += 1
            self.objects[key] = data
            return {
                "storage_key": key,
                "url": f"/artifacts/{key}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "file_size": len(data),
                "content_type": content_type,
            }

        def exists(self, key: str) -> bool:
            return key in self.objects

        def read_bytes(self, key: str) -> bytes:
            return self.objects[key]

    storage = FakeStorage()
    service = ArtifactService(storage=storage)
    payload = b"solid-bytes"

    first = service.put_generated_model(
        product_id="washer-iso7089",
        params_hash="hash-one",
        fmt="glb",
        quality="preview",
        key="washer/hash-one/preview.glb",
        data=payload,
        source="generated_parametric",
        metadata={"generator": "fake"},
    )
    second = service.put_generated_model(
        product_id="washer-iso7089",
        params_hash="hash-one",
        fmt="glb",
        quality="preview",
        key="washer/hash-one/preview.glb",
        data=payload,
        source="generated_parametric",
        metadata={"generator": "fake"},
    )

    assert first["artifact_id"] == second["artifact_id"]
    assert storage.write_calls == 1


def test_put_generated_model_repairs_missing_storage_without_creating_new_artifact():
    class FakeStorage:
        def __init__(self) -> None:
            self.write_calls = 0
            self.objects = {}

        def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> dict:
            import hashlib

            self.write_calls += 1
            self.objects[key] = data
            return {
                "storage_key": key,
                "url": f"/artifacts/{key}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "file_size": len(data),
                "content_type": content_type,
            }

        def exists(self, key: str) -> bool:
            return key in self.objects

        def read_bytes(self, key: str) -> bytes:
            return self.objects[key]

    storage = FakeStorage()
    service = ArtifactService(storage=storage)
    payload = b"repair-bytes"

    first = service.put_generated_model(
        product_id="washer-iso7089",
        params_hash="hash-two",
        fmt="glb",
        quality="preview",
        key="washer/hash-two/preview.glb",
        data=payload,
        source="generated_parametric",
        metadata={"generator": "fake"},
    )
    storage.objects.clear()

    repaired = service.put_generated_model(
        product_id="washer-iso7089",
        params_hash="hash-two",
        fmt="glb",
        quality="preview",
        key="washer/hash-two/preview.glb",
        data=payload,
        source="generated_parametric",
        metadata={"generator": "fake"},
    )

    assert first["artifact_id"] == repaired["artifact_id"]
    assert storage.write_calls == 2
    with SessionLocal() as session:
        persisted = ArtifactRepository(session).find_resolved_model(
            product_id="washer-iso7089",
            params_hash="hash-two",
            fmt="glb",
            quality="preview",
        )
        artifact_count = session.query(Artifact).count()

    assert persisted is not None
    assert persisted.id == first["artifact_id"]
    assert artifact_count == 1
