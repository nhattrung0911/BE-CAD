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
        variant_id: str | None = None,
        metadata: dict | None = None,
        uploaded_by_user_id: int | None = None,
    ) -> VendorAsset:
        asset = VendorAsset(
            product_id=product_id,
            variant_id=variant_id,
            format=fmt,
            filename=filename,
            storage_key=storage_key,
            sha256=sha256,
            file_size=file_size,
            license_status=license_status,
            validation_status=validation_status,
            metadata_json=metadata,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    def get(self, asset_id: int) -> VendorAsset | None:
        return self.session.get(VendorAsset, asset_id)

    def list_by_product(self, product_id: str | None = None) -> list[VendorAsset]:
        stmt = select(VendorAsset).order_by(VendorAsset.created_at.desc())
        if product_id:
            stmt = stmt.where(VendorAsset.product_id == product_id)
        return list(self.session.scalars(stmt))

    def update_status(
        self,
        asset: VendorAsset,
        *,
        license_status: str | None = None,
        validation_status: str | None = None,
        reviewed_by_user_id: int | None = None,
    ) -> VendorAsset:
        if license_status is not None:
            asset.license_status = license_status
        if validation_status is not None:
            asset.validation_status = validation_status
        if reviewed_by_user_id is not None:
            asset.reviewed_by_user_id = reviewed_by_user_id
        self.session.flush()
        return asset

    def find_by_storage_key(self, storage_key: str) -> VendorAsset | None:
        from sqlalchemy import select as _select
        return self.session.scalar(_select(VendorAsset).where(VendorAsset.storage_key == storage_key))

    def find_for_variant(self, variant_id: str, fmt: str) -> VendorAsset | None:
        """Variant-specific override (highest priority in resolver).

        Only files that have been explicitly approved AND validated by an admin
        are eligible — `pending` files are uploader-staged and must not be
        served to public traffic until reviewed.
        """
        if not variant_id:
            return None
        return self.session.scalar(
            select(VendorAsset)
            .where(
                VendorAsset.variant_id == variant_id,
                VendorAsset.format == fmt,
                VendorAsset.license_status == "approved",
                VendorAsset.validation_status == "valid",
            )
            .order_by(VendorAsset.created_at.desc())
        )

    def find_exact(self, product_id: str, fmt: str) -> VendorAsset | None:
        """Product-level fallback. Prefers rows that are NOT bound to a specific
        variant (variant_id IS NULL) so a generic product file doesn't accidentally
        override unrelated variants. Same approve-and-validate gating as
        ``find_for_variant``."""
        return self.session.scalar(
            select(VendorAsset)
            .where(
                VendorAsset.product_id == product_id,
                VendorAsset.variant_id.is_(None),
                VendorAsset.format == fmt,
                VendorAsset.license_status == "approved",
                VendorAsset.validation_status == "valid",
            )
            .order_by(VendorAsset.created_at.desc())
        )
