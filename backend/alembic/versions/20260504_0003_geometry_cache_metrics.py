"""geometry cache metrics

Revision ID: 20260504_0003
Revises: 20260504_0002
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260504_0003"
down_revision = "20260504_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geometry_cache_metrics",
        sa.Column("params_hash", sa.String(length=96), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("lod", sa.String(length=16), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("generation_ms", sa.Integer(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_accessed", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("params_hash"),
    )
    op.create_index("ix_geometry_cache_metrics_product_id", "geometry_cache_metrics", ["product_id"], unique=False)
    op.create_index("ix_geometry_cache_metrics_last_accessed", "geometry_cache_metrics", ["last_accessed"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_geometry_cache_metrics_last_accessed", table_name="geometry_cache_metrics")
    op.drop_index("ix_geometry_cache_metrics_product_id", table_name="geometry_cache_metrics")
    op.drop_table("geometry_cache_metrics")
