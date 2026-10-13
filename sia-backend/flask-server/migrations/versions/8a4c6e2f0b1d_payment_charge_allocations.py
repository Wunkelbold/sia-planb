"""Add audited payment allocations and current-cycle charge adjustments."""

from alembic import op
import sqlalchemy as sa


revision = "8a4c6e2f0b1d"
down_revision = "7c9e1b2d4f6a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "finance_charge",
        sa.Column("legacy_paid_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        "UPDATE finance_charge SET legacy_paid_override = true WHERE kind <> 'event_ticket' AND status = 'paid'"
    )
    op.drop_constraint("finance_charge_status_valid", "finance_charge", type_="check")
    op.create_check_constraint(
        "finance_charge_status_valid",
        "finance_charge",
        "status IN ('open', 'partially_paid', 'paid', 'cancelled', 'waived')",
    )

    op.create_table(
        "finance_payment_allocation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("charge_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("amount_cents >= 0", name="finance_payment_allocation_amount_nonnegative"),
        sa.ForeignKeyConstraint(["payment_id"], ["finance_payment.id"], ondelete="RESTRICT", name="finance_payment_allocation_payment_fkey"),
        sa.ForeignKeyConstraint(["charge_id"], ["finance_charge.id"], ondelete="RESTRICT", name="finance_payment_allocation_charge_fkey"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="finance_payment_allocation_created_by_fkey"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="finance_payment_allocation_updated_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_payment_allocation_pkey"),
        sa.UniqueConstraint("payment_id", "charge_id", name="finance_payment_allocation_payment_charge_key"),
    )
    op.create_index("ix_finance_payment_allocation_charge", "finance_payment_allocation", ["charge_id", "amount_cents"])
    op.create_index("ix_finance_payment_allocation_payment", "finance_payment_allocation", ["payment_id", "amount_cents"])

    op.create_table(
        "finance_payment_allocation_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("allocation_id", sa.Integer(), nullable=False),
        sa.Column("from_amount_cents", sa.Integer(), nullable=False),
        sa.Column("to_amount_cents", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("from_amount_cents >= 0", name="finance_payment_allocation_history_from_nonnegative"),
        sa.CheckConstraint("to_amount_cents >= 0", name="finance_payment_allocation_history_to_nonnegative"),
        sa.ForeignKeyConstraint(["allocation_id"], ["finance_payment_allocation.id"], ondelete="CASCADE", name="finance_payment_allocation_history_allocation_fkey"),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL", name="finance_payment_allocation_history_changed_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_payment_allocation_history_pkey"),
    )
    op.create_index("ix_finance_payment_allocation_history", "finance_payment_allocation_history", ["allocation_id", "changed_at"])

    op.create_table(
        "finance_charge_adjustment_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("charge_id", sa.Integer(), nullable=False),
        sa.Column("billing_run_id", sa.Integer(), nullable=True),
        sa.Column("cycle_year", sa.Integer(), nullable=False),
        sa.Column("from_amount_cents", sa.Integer(), nullable=False),
        sa.Column("to_amount_cents", sa.Integer(), nullable=False),
        sa.Column("from_fee_category", sa.String(length=20), nullable=True),
        sa.Column("to_fee_category", sa.String(length=20), nullable=True),
        sa.Column("from_name", sa.String(length=100), nullable=False),
        sa.Column("to_name", sa.String(length=100), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("from_amount_cents >= 0", name="finance_charge_adjustment_from_nonnegative"),
        sa.CheckConstraint("to_amount_cents >= 0", name="finance_charge_adjustment_to_nonnegative"),
        sa.ForeignKeyConstraint(["charge_id"], ["finance_charge.id"], ondelete="CASCADE", name="finance_charge_adjustment_charge_fkey"),
        sa.ForeignKeyConstraint(["billing_run_id"], ["finance_billing_run.id"], ondelete="SET NULL", name="finance_charge_adjustment_run_fkey"),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL", name="finance_charge_adjustment_changed_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_charge_adjustment_history_pkey"),
    )
    op.create_index("ix_finance_charge_adjustment_charge", "finance_charge_adjustment_history", ["charge_id", "changed_at"])


def downgrade():
    connection = op.get_bind()
    allocations = connection.execute(sa.text("SELECT COUNT(*) FROM finance_payment_allocation")).scalar()
    partial_charges = connection.execute(sa.text("SELECT COUNT(*) FROM finance_charge WHERE status = 'partially_paid'")).scalar()
    if allocations or partial_charges:
        raise RuntimeError("Cannot downgrade: payment allocations or partially paid charges exist.")
    op.drop_index("ix_finance_charge_adjustment_charge", table_name="finance_charge_adjustment_history")
    op.drop_table("finance_charge_adjustment_history")
    op.drop_index("ix_finance_payment_allocation_history", table_name="finance_payment_allocation_history")
    op.drop_table("finance_payment_allocation_history")
    op.drop_index("ix_finance_payment_allocation_payment", table_name="finance_payment_allocation")
    op.drop_index("ix_finance_payment_allocation_charge", table_name="finance_payment_allocation")
    op.drop_table("finance_payment_allocation")
    op.drop_constraint("finance_charge_status_valid", "finance_charge", type_="check")
    op.create_check_constraint(
        "finance_charge_status_valid",
        "finance_charge",
        "status IN ('open', 'paid', 'cancelled', 'waived')",
    )
    op.drop_column("finance_charge", "legacy_paid_override")
