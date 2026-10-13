"""Audit direct admin changes to membership status and fee category."""

from alembic import op
import sqlalchemy as sa


revision = "b92a4cf341df"
down_revision = "a81d934c2b17"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "membership_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("from_fee_category", sa.String(length=20), nullable=True),
        sa.Column("to_fee_category", sa.String(length=20), nullable=True),
        sa.Column("from_member_since", sa.Date(), nullable=True),
        sa.Column("to_member_since", sa.Date(), nullable=True),
        sa.Column("from_special_rate_cents", sa.Integer(), nullable=True),
        sa.Column("to_special_rate_cents", sa.Integer(), nullable=True),
        sa.Column("from_special_rate_valid_until", sa.Date(), nullable=True),
        sa.Column("to_special_rate_valid_until", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL", name="membership_history_changed_by_fkey"),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"], ondelete="RESTRICT", name="membership_history_membership_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="membership_history_pkey"),
    )
    op.create_index("ix_membership_history_member_changed", "membership_history", ["membership_id", "changed_at"])


def downgrade():
    op.drop_index("ix_membership_history_member_changed", table_name="membership_history")
    op.drop_table("membership_history")
