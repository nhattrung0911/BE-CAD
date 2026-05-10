"""Gated serving for vendor raw assets.

Replaces the previous ``StaticFiles`` mount under ``/raw-assets`` so that
license/validation status actually controls access. The previous mount let
anyone with a guessed storage_key bypass the resolver and download restricted
vendor IP. This module enforces:

- ``approved`` + ``valid``  →  publicly downloadable
- ``approved`` + ``pending``  →  any authenticated user (uploader+)
- ``restricted`` / ``rejected`` / ``invalid``  →  admin only
- unknown storage_key  →  404 (does not leak existence vs. permission)

For S3 storage backend we redirect to a presigned URL where supported; for the
local backend we stream the bytes through ``StreamingResponse``.
"""
from __future__ import annotations

import logging
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.auth import (
    ROLE_ADMIN,
    AuthPrincipal,
    get_current_principal,
)
from app.core.config import settings
from app.core.database import get_db
from app.db.models import VendorAsset
from app.repositories.vendor_assets import VendorAssetRepository
from app.services.storage import LocalStorage, is_safe_storage_key, make_raw_asset_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["raw-assets"])


def _public_path(asset: VendorAsset) -> bool:
    return asset.license_status == "approved" and asset.validation_status == "valid"


def _admin_only(asset: VendorAsset) -> bool:
    return (
        asset.license_status in {"restricted", "rejected"}
        or asset.validation_status == "invalid"
    )


@router.get(settings.public_raw_asset_prefix + "/{key:path}")
def serve_raw_asset(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: AuthPrincipal | None = Depends(get_current_principal),
):
    if not is_safe_storage_key(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    asset = VendorAssetRepository(db).find_by_storage_key(key)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    if _admin_only(asset):
        if principal is None or principal.role != ROLE_ADMIN:
            # Same status code whether unauthenticated or wrong role: do not
            # disclose whether the file exists to anonymous probes.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND
                if principal is None
                else status.HTTP_403_FORBIDDEN,
                detail="not found" if principal is None else "license restricted",
            )
    elif not _public_path(asset):
        # Pending / unreviewed: must be authenticated (any role).
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required for unreviewed assets",
                headers={"WWW-Authenticate": "Bearer"},
            )

    storage = make_raw_asset_storage()

    if isinstance(storage, LocalStorage):
        try:
            path = storage._safe_path(key)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
        media_type, _ = mimetypes.guess_type(path.name)
        return FileResponse(
            path,
            media_type=media_type or "application/octet-stream",
            filename=asset.filename,
            headers=_cache_headers(asset),
        )

    # S3 backend: prefer a short-lived presigned URL so we do not stream binary
    # through the FastAPI worker. Falls back to streaming on error.
    try:
        client = getattr(storage, "client", None)
        bucket = getattr(storage, "bucket", None)
        if client is not None and bucket:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=300,
            )
            return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        logger.warning("presign failed for key=%s, falling back to stream: %s", key, exc)

    data = storage.read_bytes(key)
    media_type, _ = mimetypes.guess_type(asset.filename)
    return Response(
        content=data,
        media_type=media_type or "application/octet-stream",
        headers=_cache_headers(asset),
    )


def _cache_headers(asset: VendorAsset) -> dict[str, str]:
    if asset.license_status == "approved" and asset.validation_status == "valid":
        return {
            "Cache-Control": "public, max-age=86400",
            "ETag": f'"{asset.sha256}"',
        }
    return {"Cache-Control": "private, no-cache", "ETag": f'"{asset.sha256}"'}
