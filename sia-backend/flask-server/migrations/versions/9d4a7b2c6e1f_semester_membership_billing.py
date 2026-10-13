"""Add semester billing periods and the fee categories in the contribution rules."""

from alembic import op
import sqlalchemy as sa


revision = "9d4a7b2c6e1f"
down_revision = "8a4c6e2f0b1d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("finance_charge_adjustment_history", sa.Column("from_due_date", sa.Date(), nullable=True))
    op.add_column("finance_charge_adjustment_history", sa.Column("to_due_date", sa.Date(), nullable=True))
    op.add_column(
        "finance_billing_run",
        sa.Column("period", sa.String(length=12), server_default="march", nullable=False),
    )
    op.drop_index("ix_finance_billing_run_one_issued_cycle", table_name="finance_billing_run")
    op.create_check_constraint(
        "finance_billing_run_period_valid",
        "finance_billing_run",
        "period IN ('march', 'september')",
    )
    op.create_index(
        "ix_finance_billing_run_one_issued_period",
        "finance_billing_run",
        ["cycle_year", "period"],
        unique=True,
        postgresql_where=sa.text("status = 'issued'"),
    )

    op.drop_constraint("membership_category_valid", "membership", type_="check")
    op.drop_constraint("membership_request_category_valid", "membership_request", type_="check")
    op.drop_constraint("membership_fee_rate_category_valid", "membership_fee_rate", type_="check")
    op.drop_constraint("membership_fee_rate_alumni_not_free", "membership_fee_rate", type_="check")
    op.drop_column("membership_fee_rate", "first_year_free")

    op.execute("UPDATE membership SET fee_category = 'full' WHERE fee_category = 'alumni'")
    op.execute("UPDATE membership_request SET requested_category = 'full' WHERE requested_category = 'alumni'")
    op.execute("UPDATE membership_history SET from_fee_category = 'full' WHERE from_fee_category = 'alumni'")
    op.execute("UPDATE membership_history SET to_fee_category = 'full' WHERE to_fee_category = 'alumni'")
    op.execute("UPDATE finance_charge SET fee_category_snapshot = 'full' WHERE fee_category_snapshot = 'alumni'")
    op.execute("UPDATE finance_charge_adjustment_history SET from_fee_category = 'full' WHERE from_fee_category = 'alumni'")
    op.execute("UPDATE finance_charge_adjustment_history SET to_fee_category = 'full' WHERE to_fee_category = 'alumni'")
    op.execute("UPDATE membership_fee_rate SET category = 'full' WHERE category = 'alumni'")

    op.create_check_constraint(
        "membership_category_valid",
        "membership",
        "fee_category IN ('full', 'reduced', 'student', 'training', 'exempt', 'special')",
    )
    op.create_check_constraint(
        "membership_request_category_valid",
        "membership_request",
        "requested_category IN ('full', 'reduced', 'student', 'training', 'exempt', 'special')",
    )
    op.create_check_constraint(
        "membership_fee_rate_category_valid",
        "membership_fee_rate",
        "category IN ('full', 'reduced', 'student', 'training', 'exempt')",
    )

    op.execute(
        """
        INSERT INTO membership_fee_rate (category, annual_amount_cents)
        VALUES ('reduced', 2500), ('training', 2000), ('exempt', 0)
        ON CONFLICT (category) DO NOTHING
        """
    )


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT COUNT(*) FROM finance_billing_run WHERE period = 'september'"
    )).scalar():
        raise RuntimeError("Cannot downgrade: September billing runs exist.")
    for table, column in (
        ("membership", "fee_category"),
        ("membership_request", "requested_category"),
        ("membership_history", "from_fee_category"),
        ("membership_history", "to_fee_category"),
        ("finance_charge", "fee_category_snapshot"),
        ("finance_charge_adjustment_history", "from_fee_category"),
        ("finance_charge_adjustment_history", "to_fee_category"),
    ):
        if connection.execute(sa.text(
            f"SELECT COUNT(*) FROM {table} WHERE {column} IN ('reduced', 'training', 'exempt')"
        )).scalar():
            raise RuntimeError("Cannot downgrade: new contribution categories are in use.")

    op.drop_index("ix_finance_billing_run_one_issued_period", table_name="finance_billing_run")
    op.drop_constraint("finance_billing_run_period_valid", "finance_billing_run", type_="check")
    op.drop_column("finance_billing_run", "period")
    op.drop_column("finance_charge_adjustment_history", "to_due_date")
    op.drop_column("finance_charge_adjustment_history", "from_due_date")
    op.drop_constraint("membership_category_valid", "membership", type_="check")
    op.drop_constraint("membership_request_category_valid", "membership_request", type_="check")
    op.drop_constraint("membership_fee_rate_category_valid", "membership_fee_rate", type_="check")

    op.execute("UPDATE membership SET fee_category = 'alumni' WHERE fee_category = 'full'")
    op.execute("UPDATE membership_request SET requested_category = 'alumni' WHERE requested_category = 'full'")
    op.execute("UPDATE membership_history SET from_fee_category = 'alumni' WHERE from_fee_category = 'full'")
    op.execute("UPDATE membership_history SET to_fee_category = 'alumni' WHERE to_fee_category = 'full'")
    op.execute("UPDATE finance_charge SET fee_category_snapshot = 'alumni' WHERE fee_category_snapshot = 'full'")
    op.execute("UPDATE finance_charge_adjustment_history SET from_fee_category = 'alumni' WHERE from_fee_category = 'full'")
    op.execute("UPDATE finance_charge_adjustment_history SET to_fee_category = 'alumni' WHERE to_fee_category = 'full'")
    op.execute("DELETE FROM membership_fee_rate WHERE category IN ('reduced', 'training', 'exempt')")
    op.execute("UPDATE membership_fee_rate SET category = 'alumni' WHERE category = 'full'")

    op.add_column(
        "membership_fee_rate",
        sa.Column("first_year_free", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        "membership_category_valid",
        "membership",
        "fee_category IN ('student', 'alumni', 'special')",
    )
    op.create_check_constraint(
        "membership_request_category_valid",
        "membership_request",
        "requested_category IN ('student', 'alumni', 'special')",
    )
    op.create_check_constraint(
        "membership_fee_rate_category_valid",
        "membership_fee_rate",
        "category IN ('student', 'alumni')",
    )
    op.create_check_constraint(
        "membership_fee_rate_alumni_not_free",
        "membership_fee_rate",
        "category <> 'alumni' OR first_year_free = false",
    )
    op.create_index(
        "ix_finance_billing_run_one_issued_cycle",
        "finance_billing_run",
        ["cycle_year"],
        unique=True,
        postgresql_where=sa.text("status = 'issued'"),
    )
