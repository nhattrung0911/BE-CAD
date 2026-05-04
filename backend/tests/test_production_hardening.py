"""Tests for production-hardening additions: rate limit, vendor status flip, CSV import."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import reset_for_testing
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rl():
    reset_for_testing()
    yield
    reset_for_testing()


def test_ingest_2d_rate_limit_kicks_in_after_30_calls():
    settings.admin_api_key = "test-admin-key"
    headers = {"X-Admin-API-Key": "test-admin-key"}
    body = {"product_id": "hex-bolt-iso4014", "content": "M8 d:8.0 L:30"}

    last_status = 200
    for _ in range(35):
        r = client.post("/api/v1/ingest/2d", headers=headers, json=body)
        last_status = r.status_code
        if r.status_code == 429:
            break
    assert last_status == 429


def test_vendor_asset_upload_then_flip_license_status():
    settings.admin_api_key = "test-admin-key"
    headers = {"X-Admin-API-Key": "test-admin-key"}
    upload = client.post(
        "/api/v1/vendor-assets",
        headers=headers,
        data={
            "product_id": "hex-bolt-iso4014",
            "format": "step",
            "license_status": "pending",
            "validation_status": "pending",
        },
        files={"file": ("test.step", b"ISO-10303-21;\nFAKE STEP;\nEND-ISO-10303-21;", "application/step")},
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]

    flip = client.patch(
        f"/api/v1/vendor-assets/{asset_id}/status",
        headers=headers,
        json={"license_status": "approved", "validation_status": "valid"},
    )
    assert flip.status_code == 200
    body = flip.json()
    assert body["license_status"] == "approved"
    assert body["validation_status"] == "valid"


def test_vendor_status_flip_rejects_unknown_value():
    settings.admin_api_key = "test-admin-key"
    headers = {"X-Admin-API-Key": "test-admin-key"}
    upload = client.post(
        "/api/v1/vendor-assets",
        headers=headers,
        data={"product_id": "hex-bolt-iso4014", "format": "step"},
        files={"file": ("x.step", b"x", "application/step")},
    )
    asset_id = upload.json()["id"]
    bad = client.patch(
        f"/api/v1/vendor-assets/{asset_id}/status",
        headers=headers,
        json={"license_status": "pirate"},
    )
    assert bad.status_code == 400


def test_vendor_list_filters_by_product():
    settings.admin_api_key = "test-admin-key"
    headers = {"X-Admin-API-Key": "test-admin-key"}
    response = client.get("/api/v1/vendor-assets?product_id=hex-bolt-iso4014", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    import csv as _csv
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def test_csv_importer_dry_run_reports_count():
    from app.bootstrap.import_catalog import import_catalog_csv

    csv_dir = Path(__file__).parent / "_csv_fixtures"
    csv_dir.mkdir(exist_ok=True)
    csv_path = csv_dir / "catalog_ok.csv"
    header = [
        "product_id", "family", "standard", "name",
        "variant_id", "sku", "label", "diameter_label", "material", "params",
    ]
    _write_csv(csv_path, header, [
        ["demo-bolt-x", "hex_bolt", "DEMOX", "Demo bolt",
         "demo-bolt-x-m8", "DEMO-X-M8", "M8", "M8", "steel",
         json.dumps({"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22})],
        ["demo-bolt-x", "hex_bolt", "DEMOX", "Demo bolt",
         "demo-bolt-x-m10", "DEMO-X-M10", "M10", "M10", "steel",
         json.dumps({"d": 10, "L": 40, "P": 1.5, "k": 6.4, "s": 17, "b": 26})],
    ])
    products, variants, errors = import_catalog_csv(csv_path, dry_run=True)
    assert errors == []
    assert products == 1
    assert variants == 2


def test_csv_importer_rejects_invalid_product_id():
    from app.bootstrap.import_catalog import import_catalog_csv

    csv_dir = Path(__file__).parent / "_csv_fixtures"
    csv_dir.mkdir(exist_ok=True)
    csv_path = csv_dir / "catalog_bad.csv"
    header = [
        "product_id", "family", "standard", "name",
        "variant_id", "sku", "label", "diameter_label", "material", "params",
    ]
    _write_csv(csv_path, header, [
        ["../etc/passwd", "hex_bolt", "X", "Bad",
         "bad-v", "BAD", "M8", "M8", "steel", json.dumps({"d": 8})],
    ])
    products, variants, errors = import_catalog_csv(csv_path, dry_run=True)
    assert products == 0
    assert any("product_id" in e for e in errors)


def test_button_head_iso7380_variant_resolves():
    response = client.get("/api/v1/products/button-head-iso7380/variants")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    sku_ids = {v["variant_id"] for vs in body["grouped_by_diameter"].values() for v in vs}
    assert "button-head-iso7380-m3x6" in sku_ids


def test_vendor_upload_with_variant_id_persists_field():
    settings.admin_api_key = "test-admin-key"
    headers = {"X-Admin-API-Key": "test-admin-key"}
    response = client.post(
        "/api/v1/vendor-assets",
        headers=headers,
        data={
            "product_id": "hex-bolt-iso4014",
            "variant_id": "hex-bolt-iso4014-m8x30",
            "format": "step",
            "license_status": "approved",
            "validation_status": "valid",
        },
        files={"file": ("vendor.step", b"ISO-10303-21;\nDATA;\nENDSEC;\nEND-ISO-10303-21;", "application/step")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["variant_id"] == "hex-bolt-iso4014-m8x30"
    assert body["product_id"] == "hex-bolt-iso4014"


def test_resolver_picks_variant_specific_vendor_over_product_level():
    """Per-variant vendor file must override the product-level fallback."""
    from app.core.database import SessionLocal
    from app.repositories.vendor_assets import VendorAssetRepository
    from app.schemas.model import ModelResolveRequest
    from app.services.cache_service import cache
    from app.services.model_resolver import model_resolver

    cache.clear()
    with SessionLocal() as session:
        repo = VendorAssetRepository(session)
        # Product-level (variant_id=NULL) — should NOT be returned when variant override exists
        repo.create(
            product_id="hex-bolt-iso4014",
            variant_id=None,
            fmt="step",
            filename="generic.step",
            storage_key="vendor-test/product-level.step",
            sha256="a" * 64,
            file_size=42,
            license_status="approved",
            validation_status="valid",
        )
        # Variant-specific override
        repo.create(
            product_id="hex-bolt-iso4014",
            variant_id="hex-bolt-iso4014-m8x30",
            fmt="step",
            filename="exact.step",
            storage_key="vendor-test/variant-exact.step",
            sha256="b" * 64,
            file_size=99,
            license_status="approved",
            validation_status="valid",
        )
        session.commit()

    # Mock storage exists check is not relevant here — the resolver returns vendor
    # before touching artifact storage (vendor has its own storage_key path).
    resolved = model_resolver.resolve(
        ModelResolveRequest(
            product_id="hex-bolt-iso4014",
            variant_id="hex-bolt-iso4014-m8x30",
            params={"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
            format="step",
            quality="engineering",
        )
    )
    assert resolved.status == "ready"
    assert resolved.source == "vendor_variant"
    assert resolved.artifact.sha256 == "b" * 64

    cache.clear()
    # When a different variant is asked for, fall back to product-level vendor
    resolved2 = model_resolver.resolve(
        ModelResolveRequest(
            product_id="hex-bolt-iso4014",
            variant_id="hex-bolt-iso4014-m12x50",
            params={"d": 12, "L": 50, "P": 1.75, "k": 7.5, "s": 19, "b": 30},
            format="step",
            quality="engineering",
        )
    )
    assert resolved2.status == "ready"
    assert resolved2.source == "vendor_exact"
    assert resolved2.artifact.sha256 == "a" * 64
    cache.clear()


def test_repository_find_for_variant_ignores_unapproved_status():
    from app.core.database import SessionLocal
    from app.repositories.vendor_assets import VendorAssetRepository

    with SessionLocal() as session:
        repo = VendorAssetRepository(session)
        repo.create(
            product_id="hex-bolt-iso4014",
            variant_id="hex-bolt-iso4014-m10x40",
            fmt="glb",
            filename="pending.glb",
            storage_key="vendor-test/pending.glb",
            sha256="c" * 64,
            file_size=10,
            license_status="pending",
            validation_status="pending",
        )
        session.commit()
        result = repo.find_for_variant("hex-bolt-iso4014-m10x40", "glb")
    assert result is None


def test_din933_and_iso4033_in_catalog():
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    ids = {p["product_id"] for p in response.json()}
    assert "hex-bolt-din933" in ids
    assert "hex-nut-iso4033" in ids
    assert "button-head-iso7380" in ids
