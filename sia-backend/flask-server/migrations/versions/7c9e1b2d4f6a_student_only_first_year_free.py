"""Restrict the free introductory year to the student rate."""

from alembic import op


revision = "7c9e1b2d4f6a"
down_revision = "6b8d0f3a1c5e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE membership_fee_rate SET first_year_free = false WHERE category = 'alumni'")
    op.create_check_constraint(
        "membership_fee_rate_alumni_not_free",
        "membership_fee_rate",
        "category <> 'alumni' OR first_year_free = false",
    )


def downgrade():
    op.drop_constraint("membership_fee_rate_alumni_not_free", "membership_fee_rate", type_="check")
