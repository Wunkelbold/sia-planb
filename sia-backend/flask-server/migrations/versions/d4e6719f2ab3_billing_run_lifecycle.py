"""Add auditable billing-run voiding and allow a replacement run per cycle."""

from alembic import op
import sqlalchemy as sa


revision = "d4e6719f2ab3"
down_revision = "c317fd942a6b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "finance_billing_run",
        sa.Column("run_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "finance_billing_run",
        sa.Column("status", sa.String(length=20), server_default="issued", nullable=False),
    )
    op.add_column("finance_billing_run", sa.Column("voided_by", sa.Integer(), nullable=True))
    op.add_column("finance_billing_run", sa.Column("voided_at", sa.DateTime(), nullable=True))
    op.add_column("finance_billing_run", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "finance_billing_run_voided_by_fkey",
        "finance_billing_run",
        "user",
        ["voided_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("finance_billing_run_cycle_year_key", "finance_billing_run", type_="unique")
    op.create_check_constraint(
        "finance_billing_run_number_positive",
        "finance_billing_run",
        "run_number > 0",
    )
    op.create_check_constraint(
        "finance_billing_run_status_valid",
        "finance_billing_run",
        "status IN ('issued', 'voided')",
    )
    op.create_unique_constraint(
        "finance_billing_run_cycle_run_key",
        "finance_billing_run",
        ["cycle_year", "run_number"],
    )
    op.create_index(
        "ix_finance_billing_run_one_issued_cycle",
        "finance_billing_run",
        ["cycle_year"],
        unique=True,
        postgresql_where=sa.text("status = 'issued'"),
    )

    op.drop_constraint("finance_charge_membership_cycle_key", "finance_charge", type_="unique")
    op.create_unique_constraint(
        "finance_charge_membership_run_key",
        "finance_charge",
        ["membership_id", "kind", "cycle_year", "billing_run_id"],
    )


def downgrade():
    connection = op.get_bind()
    duplicate_cycle = connection.execute(sa.text(
        "SELECT cycle_year FROM finance_billing_run GROUP BY cycle_year HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate_cycle:
        raise RuntimeError("Cannot downgrade: a billing cycle has replacement runs.")

    duplicate_charge = connection.execute(sa.text(
        """
        SELECT membership_id, kind, cycle_year
        FROM finance_charge
        GROUP BY membership_id, kind, cycle_year
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )).first()
    if duplicate_charge:
        raise RuntimeError("Cannot downgrade: a member has multiple finance charges for a cycle.")

    op.drop_constraint("finance_charge_membership_run_key", "finance_charge", type_="unique")
    op.create_unique_constraint(
        "finance_charge_membership_cycle_key",
        "finance_charge",
        ["membership_id", "kind", "cycle_year"],
    )
    op.drop_index("ix_finance_billing_run_one_issued_cycle", table_name="finance_billing_run")
    op.drop_constraint("finance_billing_run_cycle_run_key", "finance_billing_run", type_="unique")
    op.drop_constraint("finance_billing_run_status_valid", "finance_billing_run", type_="check")
    op.drop_constraint("finance_billing_run_number_positive", "finance_billing_run", type_="check")
    op.create_unique_constraint("finance_billing_run_cycle_year_key", "finance_billing_run", ["cycle_year"])
    op.drop_constraint("finance_billing_run_voided_by_fkey", "finance_billing_run", type_="foreignkey")
    op.drop_column("finance_billing_run", "void_reason")
    op.drop_column("finance_billing_run", "voided_at")
    op.drop_column("finance_billing_run", "voided_by")
    op.drop_column("finance_billing_run", "status")
    op.drop_column("finance_billing_run", "run_number")
