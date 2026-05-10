"""Authentication primitives: password hashing, JWT, and request dependencies.

Implementation uses Python stdlib only (hashlib PBKDF2-HMAC-SHA256 for passwords,
hmac + base64url for HS256 JWT). This keeps deployment portable (no bcrypt build
chain) and avoids a third-party crypto dep for the password path. The hash format
is versioned (`pbkdf2_sha256$<iters>$<salt_b64>$<hash_b64>`) so we can migrate to
argon2/bcrypt later without breaking existing rows.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.db.models import User

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 200_000
PBKDF2_ALGO = "pbkdf2_sha256"
ROLE_VIEWER = "viewer"
ROLE_UPLOADER = "uploader"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_VIEWER, ROLE_UPLOADER, ROLE_ADMIN}


# ---------- password hashing ----------

def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ALGO}${PBKDF2_ITERATIONS}${_b64u(salt)}${_b64u(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = encoded.split("$")
        if algo != PBKDF2_ALGO:
            return False
        salt = _b64u_decode(salt_b64)
        expected = _b64u_decode(hash_b64)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(derived, expected)
    except (ValueError, KeyError):
        return False


# ---------- JWT (HS256) ----------

def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(value: str) -> bytes:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + pad)


def create_access_token(*, user_id: int, role: str, ttl_seconds: int | None = None) -> str:
    secret = _require_jwt_secret()
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + (ttl_seconds or settings.jwt_ttl_minutes * 60),
        "jti": secrets.token_urlsafe(8),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = _b64u(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64u(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64u(sig)}"


class TokenError(Exception):
    pass


def decode_token(token: str) -> dict:
    secret = _require_jwt_secret()
    try:
        h_b64, p_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("Malformed token") from exc
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64u_decode(sig_b64)
    except Exception as exc:
        raise TokenError("Invalid signature encoding") from exc
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise TokenError("Invalid signature")
    try:
        header = json.loads(_b64u_decode(h_b64))
        payload = json.loads(_b64u_decode(p_b64))
    except Exception as exc:
        raise TokenError("Invalid token payload") from exc
    if header.get("alg") != "HS256":
        raise TokenError("Unsupported alg")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("Token expired")
    return payload


def _require_jwt_secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is not configured. Set it in environment / .env "
            "(min 32 chars in production)."
        )
    return settings.jwt_secret


# ---------- FastAPI dependencies ----------

@dataclass
class AuthPrincipal:
    """Identity for the current request. Either a User row, or a machine-key
    fallback (admin role, no user row) used by CLI scripts and legacy clients."""

    user: User | None
    role: str
    is_machine: bool = False

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _is_open_dev_mode() -> bool:
    """Dev convenience: when no admin key AND not production, treat all
    requests as machine-admin so legacy/local clients keep working without
    needing JWTs. Production config validator forbids this combination, so
    this branch can never trigger in a real deploy.
    """
    return (
        settings.environment != "production"
        and not settings.admin_api_key
        and settings.allow_first_admin_bootstrap
    )


def get_current_principal(
    authorization: str | None = Header(default=None),
    admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
    db: Session = Depends(get_db),
) -> AuthPrincipal | None:
    """Resolve identity. Order:
    1. Bearer JWT  → real user
    2. X-Admin-API-Key matches settings.admin_api_key  → machine-admin (CLI)
    3. Dev-mode open access (no admin key + non-prod)  → machine-admin
    4. None  → unauthenticated (route can choose to allow or reject)
    """
    token = _bearer_token(authorization)
    if token:
        try:
            payload = decode_token(token)
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
        try:
            user_id = int(payload["sub"])
        except (KeyError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return AuthPrincipal(user=user, role=user.role)

    if settings.admin_api_key and admin_api_key:
        if hmac.compare_digest(admin_api_key, settings.admin_api_key):
            return AuthPrincipal(user=None, role=ROLE_ADMIN, is_machine=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key")

    # Reject explicit-but-wrong admin key even in dev mode.
    if admin_api_key and settings.admin_api_key and admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key")

    if _is_open_dev_mode():
        return AuthPrincipal(user=None, role=ROLE_ADMIN, is_machine=True)

    return None


def require_principal(principal: AuthPrincipal | None = Depends(get_current_principal)) -> AuthPrincipal:
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_role(*roles: str):
    """Dependency factory: ensure principal has one of the given roles.
    Admin always passes."""
    allowed = set(roles) | {ROLE_ADMIN}

    def _dep(principal: AuthPrincipal = Depends(require_principal)) -> AuthPrincipal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {sorted(allowed)}",
            )
        return principal

    return _dep


def get_authenticated_user(db: Session, *, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
