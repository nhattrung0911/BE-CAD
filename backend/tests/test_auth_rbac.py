"""Auth + RBAC behavior. Verifies:

- token issuance & verification, expiry handling, tampered-signature rejection
- bootstrap of first admin without prior credentials
- role enforcement on vendor-asset and ingest endpoints
- shared-key (machine) fallback continues to work alongside JWT
"""
from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.auth import (
    ROLE_ADMIN,
    ROLE_UPLOADER,
    ROLE_VIEWER,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.rate_limit import reset_for_testing
from app.db.models import AuditLogEntry, User, VendorAsset
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_auth_state():
    # Each test starts with: a JWT secret set, no users, no vendor assets,
    # admin api key disabled (so we exercise the JWT path explicitly), and
    # rate limiter buckets reset.
    original_secret = settings.jwt_secret
    original_admin_key = settings.admin_api_key
    original_env = settings.environment
    original_bootstrap = settings.allow_first_admin_bootstrap
    settings.jwt_secret = "test-secret-key-with-enough-length-xxx"
    settings.admin_api_key = None
    settings.environment = "local"
    settings.allow_first_admin_bootstrap = True
    reset_for_testing()
    with SessionLocal() as db:
        db.execute(delete(VendorAsset))
        db.execute(delete(AuditLogEntry))
        db.execute(delete(User))
        db.commit()
    yield
    settings.jwt_secret = original_secret
    settings.admin_api_key = original_admin_key
    settings.environment = original_env
    settings.allow_first_admin_bootstrap = original_bootstrap
    reset_for_testing()
    with SessionLocal() as db:
        db.execute(delete(VendorAsset))
        db.execute(delete(AuditLogEntry))
        db.execute(delete(User))
        db.commit()


def _create_user(email: str, password: str, role: str) -> int:
    with SessionLocal() as db:
        user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
        db.add(user)
        db.commit()
        return user.id


def _login(email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------- password + token primitives ----------

def test_password_hash_and_verify_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_password_hash_rejects_short_password():
    with pytest.raises(ValueError):
        hash_password("short")


def test_token_decode_rejects_tampered_signature():
    token = create_access_token(user_id=1, role=ROLE_ADMIN)
    head, payload, _ = token.split(".")
    tampered = f"{head}.{payload}.AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    from app.core.auth import TokenError

    with pytest.raises(TokenError):
        decode_token(tampered)


def test_token_decode_rejects_expired_token():
    token = create_access_token(user_id=1, role=ROLE_ADMIN, ttl_seconds=-1)
    from app.core.auth import TokenError

    with pytest.raises(TokenError):
        decode_token(token)


# ---------- registration & login flow ----------

def test_first_admin_bootstrap_creates_admin_without_auth():
    # Disable dev-mode open access so bootstrap is the only way in.
    settings.admin_api_key = "irrelevant-key-32-characters-long-ok"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "password": "passw0rd!", "role": "viewer"},
    )
    assert resp.status_code == 201
    body = resp.json()
    # Bootstrap forces admin regardless of requested role.
    assert body["role"] == ROLE_ADMIN
    assert body["email"] == "first@example.com"


def test_register_after_bootstrap_requires_admin_token():
    _create_user("admin@x.com", "adminpass", ROLE_ADMIN)
    settings.admin_api_key = "irrelevant-key-32-characters-long-ok"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "another@x.com", "password": "anotherpass", "role": "uploader"},
    )
    assert resp.status_code == 403


def test_login_returns_token_for_valid_credentials():
    _create_user("u@x.com", "uploaderpass", ROLE_UPLOADER)
    token = _login("u@x.com", "uploaderpass")
    me = client.get("/api/v1/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["role"] == ROLE_UPLOADER


def test_login_rejects_wrong_password():
    _create_user("u@x.com", "uploaderpass", ROLE_UPLOADER)
    resp = client.post("/api/v1/auth/login", json={"email": "u@x.com", "password": "nope1234"})
    assert resp.status_code == 401


# ---------- RBAC on vendor-asset endpoints ----------

def test_vendor_asset_upload_requires_uploader_role():
    settings.admin_api_key = "irrelevant-key-32-characters-long-ok"  # disable dev bypass
    _create_user("v@x.com", "viewerpass", ROLE_VIEWER)
    token = _login("v@x.com", "viewerpass")
    resp = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("a.glb", io.BytesIO(b"x"), "model/gltf-binary")},
        headers=_bearer(token),
    )
    assert resp.status_code == 403


def test_uploader_cannot_self_approve_files():
    settings.admin_api_key = "irrelevant-key-32-characters-long-ok"
    _create_user("u@x.com", "uploaderpass", ROLE_UPLOADER)
    token = _login("u@x.com", "uploaderpass")
    resp = client.post(
        "/api/v1/vendor-assets",
        data={
            "product_id": "hex-bolt-iso4014",
            "format": "glb",
            "license_status": "approved",
            "validation_status": "valid",
        },
        files={"file": ("a.glb", io.BytesIO(b"x"), "model/gltf-binary")},
        headers=_bearer(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    # Server forces these to pending — uploaders may not approve their own files.
    assert body["license_status"] == "pending"
    assert body["validation_status"] == "pending"


def test_uploader_cannot_review_status_only_admin():
    settings.admin_api_key = "irrelevant-key-32-characters-long-ok"
    _create_user("u@x.com", "uploaderpass", ROLE_UPLOADER)
    admin_id = _create_user("a@x.com", "adminpass", ROLE_ADMIN)
    uploader_token = _login("u@x.com", "uploaderpass")
    admin_token = _login("a@x.com", "adminpass")

    upload = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("a.glb", io.BytesIO(b"x"), "model/gltf-binary")},
        headers=_bearer(uploader_token),
    )
    asset_id = upload.json()["id"]

    forbidden = client.patch(
        f"/api/v1/vendor-assets/{asset_id}/status",
        json={"license_status": "approved", "validation_status": "valid"},
        headers=_bearer(uploader_token),
    )
    assert forbidden.status_code == 403

    ok = client.patch(
        f"/api/v1/vendor-assets/{asset_id}/status",
        json={"license_status": "approved", "validation_status": "valid"},
        headers=_bearer(admin_token),
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["license_status"] == "approved"
    assert body["validation_status"] == "valid"
    assert body["reviewed_by_user_id"] == admin_id


def test_admin_api_key_fallback_still_works():
    settings.admin_api_key = "machine-key-32-characters-long-padd"
    resp = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("a.glb", io.BytesIO(b"x"), "model/gltf-binary")},
        headers={"X-Admin-API-Key": "machine-key-32-characters-long-padd"},
    )
    assert resp.status_code == 201


def test_invalid_admin_api_key_is_rejected_even_in_dev():
    settings.admin_api_key = "machine-key-32-characters-long-padd"
    resp = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("a.glb", io.BytesIO(b"x"), "model/gltf-binary")},
        headers={"X-Admin-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


# ---------- audit log ----------

def test_upload_writes_audit_entry_with_actor_and_target():
    settings.admin_api_key = "irrelevant-key-32-characters-long-ok"
    user_id = _create_user("u@x.com", "uploaderpass", ROLE_UPLOADER)
    token = _login("u@x.com", "uploaderpass")
    upload = client.post(
        "/api/v1/vendor-assets",
        data={"product_id": "hex-bolt-iso4014", "format": "glb"},
        files={"file": ("a.glb", io.BytesIO(b"x"), "model/gltf-binary")},
        headers=_bearer(token),
    )
    asset_id = upload.json()["id"]
    with SessionLocal() as db:
        entries = db.query(AuditLogEntry).filter(AuditLogEntry.action == "vendor_asset.upload").all()
    actions = [(e.user_id, e.target_id) for e in entries]
    assert (user_id, str(asset_id)) in actions
