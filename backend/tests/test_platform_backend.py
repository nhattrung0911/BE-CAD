import io

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.repositories.artifacts import ArtifactRepository
from app.repositories.vendor_assets import VendorAssetRepository
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
            "validation_status": "pending",
        },
        files={"file": ("bolt.step", io.BytesIO(payload), "application/step")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["product_id"] == "hex-bolt-iso4014"
    assert body["format"] == "step"
    assert body["license_status"] == "approved"
    assert body["validation_status"] == "pending"
    assert body["sha256"]
    assert body["storage_key"].endswith("/bolt.step")

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
    response = client.post(
        "/api/v1/models/resolve",
        json={
            "product_id": "hex-bolt-iso4014",
            "params": {"d": 8, "L": 40, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
            "format": "step",
            "quality": "engineering",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["source"] == "queued_parametric"
    assert body["job_id"].startswith("job_")


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
