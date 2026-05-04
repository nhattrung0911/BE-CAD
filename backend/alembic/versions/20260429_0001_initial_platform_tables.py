"""initial platform tables

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260429_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("quality", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("params_hash", sa.String(length=96), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "params_hash", "format", "quality", name="uq_artifacts_resolved_model"),
        sa.UniqueConstraint("storage_key", name="uq_artifacts_storage_key"),
    )
    op.create_index(op.f("ix_artifacts_params_hash"), "artifacts", ["params_hash"], unique=False)
    op.create_index(op.f("ix_artifacts_product_id"), "artifacts", ["product_id"], unique=False)

    op.create_table(
        "vendor_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("license_status", sa.String(length=32), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_vendor_assets_format"), "vendor_assets", ["format"], unique=False)
    op.create_index(op.f("ix_vendor_assets_product_id"), "vendor_assets", ["product_id"], unique=False)
    op.create_index(op.f("ix_vendor_assets_sha256"), "vendor_assets", ["sha256"], unique=False)

    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("queue_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("quality", sa.String(length=32), nullable=False),
        sa.Column("params_hash", sa.String(length=96), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("result_artifact_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(op.f("ix_generation_jobs_job_id"), "generation_jobs", ["job_id"], unique=False)
    op.create_index(op.f("ix_generation_jobs_params_hash"), "generation_jobs", ["params_hash"], unique=False)
    op.create_index(op.f("ix_generation_jobs_product_id"), "generation_jobs", ["product_id"], unique=False)
    op.create_index(op.f("ix_generation_jobs_queue_name"), "generation_jobs", ["queue_name"], unique=False)

    op.create_table(
        "parsed_drawings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("dimensions_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parsed_drawings_product_id"), "parsed_drawings", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parsed_drawings_product_id"), table_name="parsed_drawings")
    op.drop_table("parsed_drawings")
    op.drop_index(op.f("ix_generation_jobs_queue_name"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_product_id"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_params_hash"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_job_id"), table_name="generation_jobs")
    op.drop_table("generation_jobs")
    op.drop_index(op.f("ix_vendor_assets_sha256"), table_name="vendor_assets")
    op.drop_index(op.f("ix_vendor_assets_product_id"), table_name="vendor_assets")
    op.drop_index(op.f("ix_vendor_assets_format"), table_name="vendor_assets")
    op.drop_table("vendor_assets")
    op.drop_index(op.f("ix_artifacts_product_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_params_hash"), table_name="artifacts")
    op.drop_table("artifacts")
