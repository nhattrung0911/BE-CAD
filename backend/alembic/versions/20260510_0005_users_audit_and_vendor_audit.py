"""users, audit_log, and vendor_assets audit columns

Revision ID: 20260510_0005
Revises: 20260505_0004
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0005"
down_revision = "20260505_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    op.add_column(
        "vendor_assets",
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "vendor_assets",
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_vendor_assets_uploaded_by_user_id",
        "vendor_assets",
        ["uploaded_by_user_id"],
    )
    op.create_index(
        "ix_vendor_assets_reviewed_by_user_id",
        "vendor_assets",
        ["reviewed_by_user_id"],
    )
    with op.batch_alter_table("vendor_assets") as batch:
        batch.create_foreign_key(
            "fk_vendor_assets_uploaded_by_user_id_users",
            "users",
            ["uploaded_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_vendor_assets_reviewed_by_user_id_users",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("vendor_assets") as batch:
        batch.drop_constraint("fk_vendor_assets_reviewed_by_user_id_users", type_="foreignkey")
        batch.drop_constraint("fk_vendor_assets_uploaded_by_user_id_users", type_="foreignkey")
    op.drop_index("ix_vendor_assets_reviewed_by_user_id", table_name="vendor_assets")
    op.drop_index("ix_vendor_assets_uploaded_by_user_id", table_name="vendor_assets")
    op.drop_column("vendor_assets", "reviewed_by_user_id")
    op.drop_column("vendor_assets", "uploaded_by_user_id")

    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
