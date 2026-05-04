from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_artifacts_storage_key"),
        UniqueConstraint("product_id", "params_hash", "format", "quality", name="uq_artifacts_resolved_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    quality: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    params_hash: Mapped[str | None] = mapped_column(String(96), index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class VendorAsset(TimestampMixin, Base):
    __tablename__ = "vendor_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    license_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class GenerationJob(TimestampMixin, Base):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    queue_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    product_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    quality: Mapped[str] = mapped_column(String(32), nullable=False)
    params_hash: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_artifact_id: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(String(1024))


class ParsedDrawing(TimestampMixin, Base):
    __tablename__ = "parsed_drawings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    dimensions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class CatalogProduct(TimestampMixin, Base):
    __tablename__ = "catalog_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    standard: Mapped[str] = mapped_column(String(64), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="mm", nullable=False)


class CatalogParameterSpec(TimestampMixin, Base):
    __tablename__ = "catalog_parameter_specs"
    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_catalog_parameter_specs_product_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("catalog_products.product_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="number", nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="mm", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    values_json: Mapped[list | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CatalogVariant(TimestampMixin, Base):
    __tablename__ = "catalog_variants"
    __table_args__ = (
        UniqueConstraint("variant_id", name="uq_catalog_variants_variant_id"),
        UniqueConstraint("sku", name="uq_catalog_variants_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("catalog_products.product_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    diameter_label: Mapped[str] = mapped_column(String(64), nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    material: Mapped[str] = mapped_column(String(64), default="steel", nullable=False)
