from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import VendorAsset


class VendorAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        product_id: str,
        fmt: str,
        filename: str,
        storage_key: str,
        sha256: str,
        file_size: int,
        license_status: str,
        validation_status: str,
        metadata: dict | None = None,
    ) -> VendorAsset:
        asset = VendorAsset(
            product_id=product_id,
            format=fmt,
            filename=filename,
            storage_key=storage_key,
            sha256=sha256,
            file_size=file_size,
            license_status=license_status,
            validation_status=validation_status,
            metadata_json=metadata,
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    def find_exact(self, product_id: str, fmt: str) -> VendorAsset | None:
        return self.session.scalar(
            select(VendorAsset)
            .where(
                VendorAsset.product_id == product_id,
                VendorAsset.format == fmt,
                VendorAsset.license_status == "approved",
                VendorAsset.validation_status.in_(["valid", "pending"]),
            )
            .order_by(VendorAsset.validation_status.desc(), VendorAsset.created_at.desc())
        )
