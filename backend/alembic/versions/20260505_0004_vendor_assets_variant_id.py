"""vendor_assets.variant_id for per-variant override

Revision ID: 20260505_0004
Revises: 20260504_0003
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260505_0004"
down_revision = "20260504_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vendor_assets",
        sa.Column("variant_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_vendor_assets_variant_id"),
        "vendor_assets",
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vendor_assets_variant_id"), table_name="vendor_assets")
    op.drop_column("vendor_assets", "variant_id")
