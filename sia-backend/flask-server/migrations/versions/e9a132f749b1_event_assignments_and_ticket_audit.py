"""Add auditable event assignments and manual ticket payment status history.

Existing registrations, payments, and financial memberships are not changed.
"""

from alembic import op
import sqlalchemy as sa


revision = "e9a132f749b1"
down_revision = "d4e6719f2ab3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("registration_userFK_fkey", "registration", type_="foreignkey")
    op.create_foreign_key(
        "registration_userFK_fkey", "registration", "user", ["userFK"], ["id"], ondelete="RESTRICT"
    )

    op.add_column("registration", sa.Column("created_by", sa.Integer(), nullable=True))
    op.add_column("registration", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("registration", sa.Column("cancelled_by", sa.Integer(), nullable=True))
    op.add_column("registration", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "registration_created_by_fkey", "registration", "user", ["created_by"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "registration_cancelled_by_fkey", "registration", "user", ["cancelled_by"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_registration_active_user_option", "registration", ["userFK", "rmFK", "cancelled_at"])

    op.add_column("duty", sa.Column("joined_timestamp", sa.DateTime(), nullable=True))
    op.add_column("duty", sa.Column("assigned_by", sa.Integer(), nullable=True))
    op.create_foreign_key("duty_assigned_by_fkey", "duty", "user", ["assigned_by"], ["id"], ondelete="SET NULL")

    op.add_column("assistant", sa.Column("assigned_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "assistant_assigned_by_fkey", "assistant", "user", ["assigned_by"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "registration_payment_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("from_paid", sa.Boolean(), nullable=False),
        sa.Column("to_paid", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["registration_id"], ["registration.id"], ondelete="CASCADE", name="registration_payment_history_registration_fkey"
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL", name="registration_payment_history_changed_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="registration_payment_history_pkey"),
    )
    op.create_index(
        "ix_registration_payment_history", "registration_payment_history", ["registration_id", "changed_at"]
    )


def downgrade():
    op.drop_index("ix_registration_payment_history", table_name="registration_payment_history")
    op.drop_table("registration_payment_history")

    op.drop_constraint("assistant_assigned_by_fkey", "assistant", type_="foreignkey")
    op.drop_column("assistant", "assigned_by")

    op.drop_constraint("duty_assigned_by_fkey", "duty", type_="foreignkey")
    op.drop_column("duty", "assigned_by")
    op.drop_column("duty", "joined_timestamp")

    op.drop_index("ix_registration_active_user_option", table_name="registration")
    op.drop_constraint("registration_cancelled_by_fkey", "registration", type_="foreignkey")
    op.drop_constraint("registration_created_by_fkey", "registration", type_="foreignkey")
    op.drop_column("registration", "cancel_reason")
    op.drop_column("registration", "cancelled_by")
    op.drop_column("registration", "cancelled_at")
    op.drop_column("registration", "created_by")
    op.drop_constraint("registration_userFK_fkey", "registration", type_="foreignkey")
    op.create_foreign_key(
        "registration_userFK_fkey", "registration", "user", ["userFK"], ["id"], ondelete="CASCADE"
    )
