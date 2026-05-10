"""Verify that raw vendor files are no longer served by anonymous static mounts.

The old StaticFiles mount let anyone download by guessing storage_key. The new
gated route enforces the license/validation matrix:
- approved + valid       → public
- approved + pending     → any authenticated user
- restricted/invalid     → admin only
- unknown key            → 404
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.auth import ROLE_ADMIN, ROLE_UPLOADER, ROLE_VIEWER, hash_password
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.rate_limit import reset_for_testing
from app.db.models import AuditLogEntry, User, VendorAsset
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate():
    original_secret = settings.jwt_secret
    original_admin_key = settings.admin_api_key
    settings.jwt_secret = "test-secret-key-with-enough-length-xxx"
    settings.admin_api_key = "machine-key-32-characters-long-padd"  # disable dev bypass
    reset_for_testing()
    with SessionLocal() as db:
        db.execute(delete(VendorAsset))
        db.execute(delete(AuditLogEntry))
        db.execute(delete(User))
        db.commit()
    yield
    settings.jwt_secret = original_secret
    settings.admin_api_key = original_admin_key
    reset_for_testing()
    with SessionLocal() as db:
        db.execute(delete(VendorAsset))
        db.execute(delete(AuditLogEntry))
        db.execute(delete(User))
        db.commit()


def _user(email: str, password: str, role: str) -> str:
    with SessionLocal() as db:
        u = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
        db.add(u)
        db.commit()
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _upload(license_status: str, validation_status: str) -> str:
    """Upload as machine-admin (so we can choose any status), return storage_key."""
    resp = client.post(
        "/api/v1/vendor-assets",
        data={
            "product_id": "hex-bolt-iso4014",
            "format": "glb",
            "license_status": license_status,
            "validation_status": validation_status,
        },
        files={"file": (f"{license_status}.glb", io.BytesIO(b"vendor-bytes"), "model/gltf-binary")},
        headers={"X-Admin-API-Key": settings.admin_api_key},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["storage_key"]


def _path(storage_key: str) -> str:
    return f"{settings.public_raw_asset_prefix}/{storage_key}"


def test_approved_and_valid_is_public():
    key = _upload("approved", "valid")
    resp = client.get(_path(key))
    assert resp.status_code == 200
    assert resp.content == b"vendor-bytes"
    assert "max-age" in resp.headers.get("cache-control", "")


def test_pending_requires_authentication():
    key = _upload("approved", "pending")
    anon = client.get(_path(key))
    assert anon.status_code == 401
    assert "WWW-Authenticate" in anon.headers

    token = _user("v@x.com", "viewerpass", ROLE_VIEWER)
    auth = client.get(_path(key), headers={"Authorization": f"Bearer {token}"})
    assert auth.status_code == 200


def test_restricted_returns_404_for_anonymous_and_403_for_non_admin():
    key = _upload("restricted", "valid")
    anon = client.get(_path(key))
    # Anonymous gets 404 to avoid disclosing existence.
    assert anon.status_code == 404

    uploader_token = _user("u@x.com", "uploaderpass", ROLE_UPLOADER)
    forbidden = client.get(_path(key), headers={"Authorization": f"Bearer {uploader_token}"})
    assert forbidden.status_code == 403


def test_restricted_is_served_to_admin():
    key = _upload("restricted", "valid")
    admin_token = _user("a@x.com", "adminpass", ROLE_ADMIN)
    ok = client.get(_path(key), headers={"Authorization": f"Bearer {admin_token}"})
    assert ok.status_code == 200
    assert ok.content == b"vendor-bytes"


def test_unknown_storage_key_returns_404():
    resp = client.get(_path("nope/missing.glb"))
    assert resp.status_code == 404


def test_path_traversal_storage_key_is_rejected():
    resp = client.get(f"{settings.public_raw_asset_prefix}/../../etc/passwd")
    # FastAPI normalizes ../ in the URL but our key safety check + DB lookup miss → 404.
    assert resp.status_code == 404
