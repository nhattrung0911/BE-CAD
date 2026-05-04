from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.core.security import require_admin_api_key
from app.repositories.vendor_assets import VendorAssetRepository
from app.schemas.vendor_asset import VendorAssetResponse
from app.services.cache_service import cache
from app.services.storage import make_raw_asset_storage, safe_storage_segment

_vendor_upload_limit = rate_limit(name="vendor_upload", limit=20, window_seconds=60.0)
_vendor_admin_limit = rate_limit(name="vendor_admin", limit=60, window_seconds=60.0)

router = APIRouter(prefix="/vendor-assets", tags=["vendor-assets"])

SUPPORTED_FORMATS = {"glb", "step", "stl"}
SUPPORTED_LICENSE_STATUSES = {"pending", "approved", "restricted", "rejected"}
SUPPORTED_VALIDATION_STATUSES = {"pending", "valid", "invalid"}


@router.post("", response_model=VendorAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_vendor_asset(
    product_id: str = Form(...),
    format: str = Form(...),
    license_status: str = Form("pending"),
    validation_status: str = Form("pending"),
    variant_id: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
    __: None = Depends(_vendor_upload_limit),
):
    data = await file.read()
    validation_errors = _validate_vendor_asset_fields(format, license_status, validation_status)
    if validation_errors:
        raise HTTPException(status_code=400, detail=validation_errors)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded asset exceeds MAX_UPLOAD_BYTES")
    storage = make_raw_asset_storage()
    try:
        safe_product_id = safe_storage_segment(product_id)
        safe_format = safe_storage_segment(format)
        filename = safe_storage_segment(file.filename or f"asset.{format}")
        # Variant scoping in the storage path keeps per-variant uploads isolated
        # so a future re-upload doesn't collide with a different variant's file.
        if variant_id:
            safe_variant_id = safe_storage_segment(variant_id)
            key = f"{safe_product_id}/{safe_format}/{safe_variant_id}/{filename}"
        else:
            key = f"{safe_product_id}/{safe_format}/{filename}"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    stored = storage.put_bytes(key, data, content_type=file.content_type)
    asset = VendorAssetRepository(db).create(
        product_id=product_id,
        variant_id=variant_id or None,
        fmt=format,
        filename=filename,
        storage_key=stored["storage_key"],
        sha256=stored["sha256"],
        file_size=stored["file_size"],
        license_status=license_status,
        validation_status=validation_status,
    )
    db.commit()
    return VendorAssetResponse(
        id=asset.id,
        product_id=asset.product_id,
        variant_id=asset.variant_id,
        format=asset.format,
        filename=asset.filename,
        storage_key=asset.storage_key,
        url=stored["url"],
        sha256=asset.sha256,
        file_size=asset.file_size,
        license_status=asset.license_status,
        validation_status=asset.validation_status,
    )


class VendorAssetStatusUpdate(BaseModel):
    license_status: str | None = None
    validation_status: str | None = None


@router.get("", response_model=list[VendorAssetResponse])
def list_vendor_assets(
    product_id: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
    __: None = Depends(_vendor_admin_limit),
):
    repo = VendorAssetRepository(db)
    rows = repo.list_by_product(product_id)
    return [
        VendorAssetResponse(
            id=a.id,
            product_id=a.product_id,
            variant_id=a.variant_id,
            format=a.format,
            filename=a.filename,
            storage_key=a.storage_key,
            url=f"{settings.public_raw_asset_prefix}/{a.storage_key}",
            sha256=a.sha256,
            file_size=a.file_size,
            license_status=a.license_status,
            validation_status=a.validation_status,
        )
        for a in rows
    ]


@router.patch("/{asset_id}/status", response_model=VendorAssetResponse)
def update_vendor_asset_status(
    asset_id: int,
    payload: VendorAssetStatusUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
    __: None = Depends(_vendor_admin_limit),
):
    if payload.license_status is None and payload.validation_status is None:
        raise HTTPException(status_code=400, detail="At least one of license_status or validation_status is required")
    if payload.license_status is not None and payload.license_status not in SUPPORTED_LICENSE_STATUSES:
        raise HTTPException(status_code=400, detail={"license_status": "unsupported"})
    if payload.validation_status is not None and payload.validation_status not in SUPPORTED_VALIDATION_STATUSES:
        raise HTTPException(status_code=400, detail={"validation_status": "unsupported"})

    repo = VendorAssetRepository(db)
    asset = repo.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="vendor asset not found")
    repo.update_status(
        asset,
        license_status=payload.license_status,
        validation_status=payload.validation_status,
    )
    db.commit()
    # Invalidate any cached resolver entries for this product/format so the
    # next request re-runs the resolver and picks up the new status.
    cache.clear()
    return VendorAssetResponse(
        id=asset.id,
        product_id=asset.product_id,
        variant_id=asset.variant_id,
        format=asset.format,
        filename=asset.filename,
        storage_key=asset.storage_key,
        url=f"{settings.public_raw_asset_prefix}/{asset.storage_key}",
        sha256=asset.sha256,
        file_size=asset.file_size,
        license_status=asset.license_status,
        validation_status=asset.validation_status,
    )


def _validate_vendor_asset_fields(format: str, license_status: str, validation_status: str) -> dict[str, str]:
    errors = {}
    if format not in SUPPORTED_FORMATS:
        errors["format"] = "unsupported"
    if license_status not in SUPPORTED_LICENSE_STATUSES:
        errors["license_status"] = "unsupported"
    if validation_status not in SUPPORTED_VALIDATION_STATUSES:
        errors["validation_status"] = "unsupported"
    return errors
