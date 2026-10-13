"""Add the public drink menu tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e2b7c4a9d3f1"
down_revision = "9d4a7b2c6e1f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drink_menu_section",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("subtitle", sa.String(length=200), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("show_price", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="drink_menu_section_price_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="drink_menu_section_created_by_fkey"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="drink_menu_section_updated_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="drink_menu_section_pkey"),
        sa.UniqueConstraint("uid", name="drink_menu_section_uid_key"),
    )
    op.create_index(
        "ix_drink_menu_section_active_order",
        "drink_menu_section",
        ["is_active", "sort_order"],
    )

    op.create_table(
        "drink_menu_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("group_label", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("volume_label", sa.String(length=40), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("show_price", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="drink_menu_item_price_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="drink_menu_item_created_by_fkey"),
        sa.ForeignKeyConstraint(["section_id"], ["drink_menu_section.id"], ondelete="CASCADE", name="drink_menu_item_section_id_fkey"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="drink_menu_item_updated_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="drink_menu_item_pkey"),
        sa.UniqueConstraint("uid", name="drink_menu_item_uid_key"),
    )
    op.create_index(
        "ix_drink_menu_item_section_order",
        "drink_menu_item",
        ["section_id", "sort_order"],
    )


def downgrade():
    op.drop_index("ix_drink_menu_item_section_order", table_name="drink_menu_item")
    op.drop_table("drink_menu_item")
    op.drop_index("ix_drink_menu_section_active_order", table_name="drink_menu_section")
    op.drop_table("drink_menu_section")
