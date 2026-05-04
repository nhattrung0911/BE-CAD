"""add catalog tables

Revision ID: 20260504_0002
Revises: 20260429_0001
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260504_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("standard", sa.String(length=64), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    op.create_index(op.f("ix_catalog_products_product_id"), "catalog_products", ["product_id"], unique=False)

    op.create_table(
        "catalog_parameter_specs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["catalog_products.product_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "name", name="uq_catalog_parameter_specs_product_name"),
    )
    op.create_index(
        op.f("ix_catalog_parameter_specs_product_id"),
        "catalog_parameter_specs",
        ["product_id"],
        unique=False,
    )

    op.create_table(
        "catalog_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.String(length=128), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("diameter_label", sa.String(length=64), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("material", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["catalog_products.product_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="uq_catalog_variants_sku"),
        sa.UniqueConstraint("variant_id", name="uq_catalog_variants_variant_id"),
    )
    op.create_index(op.f("ix_catalog_variants_product_id"), "catalog_variants", ["product_id"], unique=False)
    op.create_index(op.f("ix_catalog_variants_variant_id"), "catalog_variants", ["variant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_catalog_variants_variant_id"), table_name="catalog_variants")
    op.drop_index(op.f("ix_catalog_variants_product_id"), table_name="catalog_variants")
    op.drop_table("catalog_variants")
    op.drop_index(op.f("ix_catalog_parameter_specs_product_id"), table_name="catalog_parameter_specs")
    op.drop_table("catalog_parameter_specs")
    op.drop_index(op.f("ix_catalog_products_product_id"), table_name="catalog_products")
    op.drop_table("catalog_products")
