from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin_api_key
from app.repositories.vendor_assets import VendorAssetRepository
from app.schemas.vendor_asset import VendorAssetResponse
from app.services.storage import make_raw_asset_storage, safe_storage_segment

router = APIRouter(prefix="/vendor-assets", tags=["vendor-assets"])


@router.post("", response_model=VendorAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_vendor_asset(
    product_id: str = Form(...),
    format: str = Form(...),
    license_status: str = Form("pending"),
    validation_status: str = Form("pending"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    data = await file.read()
    storage = make_raw_asset_storage()
    try:
        safe_product_id = safe_storage_segment(product_id)
        safe_format = safe_storage_segment(format)
        filename = safe_storage_segment(file.filename or f"asset.{format}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    key = f"{safe_product_id}/{safe_format}/{filename}"
    stored = storage.put_bytes(key, data, content_type=file.content_type)
    asset = VendorAssetRepository(db).create(
        product_id=product_id,
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
        format=asset.format,
        filename=asset.filename,
        storage_key=asset.storage_key,
        url=stored["url"],
        sha256=asset.sha256,
        file_size=asset.file_size,
        license_status=asset.license_status,
        validation_status=asset.validation_status,
    )
