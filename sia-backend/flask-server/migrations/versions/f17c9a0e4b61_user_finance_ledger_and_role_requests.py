"""Unify user-owned billing and add admin-reviewed role requests.

The migration changes schema only; it does not create ticket charges, alter
payment statuses, or create Finance memberships for any user.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f17c9a0e4b61"
down_revision = "e9a132f749b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "roles",
        sa.Column("requestable_on_change", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_table(
        "user_role_request",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("from_role", sa.Text(), nullable=False),
        sa.Column("requested_role", sa.Text(), nullable=False),
        sa.Column("request_note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="user_role_request_status_valid"),
        sa.CheckConstraint("from_role <> requested_role", name="user_role_request_distinct_roles"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE", name="user_role_request_user_fkey"),
        sa.ForeignKeyConstraint(["from_role"], ["roles.name"], ondelete="RESTRICT", name="user_role_request_from_role_fkey"),
        sa.ForeignKeyConstraint(["requested_role"], ["roles.name"], ondelete="RESTRICT", name="user_role_request_requested_role_fkey"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"], ondelete="SET NULL", name="user_role_request_reviewed_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="user_role_request_pkey"),
        sa.UniqueConstraint("uid", name="user_role_request_uid_key"),
    )
    op.create_index("ix_user_role_request_status", "user_role_request", ["status", "submitted_at"])
    op.create_index(
        "uq_user_role_request_pending",
        "user_role_request",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.alter_column("finance_charge", "membership_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("finance_charge", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("finance_charge", sa.Column("registration_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "finance_charge_user_id_fkey", "finance_charge", "user", ["user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "finance_charge_registration_id_fkey",
        "finance_charge",
        "registration",
        ["registration_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("finance_charge_kind_valid", "finance_charge", type_="check")
    op.create_check_constraint(
        "finance_charge_kind_valid", "finance_charge", "kind IN ('drink', 'membership', 'event_ticket')"
    )
    op.create_check_constraint(
        "finance_charge_owner_required", "finance_charge", "membership_id IS NOT NULL OR user_id IS NOT NULL"
    )
    op.create_check_constraint(
        "finance_charge_event_ticket_registration_required",
        "finance_charge",
        "kind <> 'event_ticket' OR (user_id IS NOT NULL AND registration_id IS NOT NULL)",
    )
    op.create_unique_constraint("finance_charge_registration_key", "finance_charge", ["registration_id"])
    op.create_index("ix_finance_charge_user_status", "finance_charge", ["user_id", "status", "created_at"])

    op.alter_column("finance_payment", "membership_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("finance_payment", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "finance_payment_user_id_fkey", "finance_payment", "user", ["user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint(
        "finance_payment_owner_required", "finance_payment", "membership_id IS NOT NULL OR user_id IS NOT NULL"
    )
    op.create_index("ix_finance_payment_user_received", "finance_payment", ["user_id", "received_at"])

    op.alter_column("finance_reminder", "membership_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("finance_reminder", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "finance_reminder_user_id_fkey", "finance_reminder", "user", ["user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint(
        "finance_reminder_owner_required", "finance_reminder", "membership_id IS NOT NULL OR user_id IS NOT NULL"
    )
    op.create_index("ix_finance_reminder_user", "finance_reminder", ["user_id", "sent_at"])


def downgrade():
    connection = op.get_bind()
    new_charges = connection.execute(sa.text(
        "SELECT COUNT(*) FROM finance_charge WHERE kind = 'event_ticket' OR user_id IS NOT NULL"
    )).scalar()
    new_payments = connection.execute(sa.text(
        "SELECT COUNT(*) FROM finance_payment WHERE user_id IS NOT NULL"
    )).scalar()
    new_reminders = connection.execute(sa.text(
        "SELECT COUNT(*) FROM finance_reminder WHERE user_id IS NOT NULL"
    )).scalar()
    role_requests = connection.execute(sa.text("SELECT COUNT(*) FROM user_role_request")).scalar()
    if new_charges or new_payments or new_reminders or role_requests:
        raise RuntimeError("Cannot downgrade: user-owned charges, payments, reminders, or role requests exist.")

    op.drop_index("ix_finance_reminder_user", table_name="finance_reminder")
    op.drop_constraint("finance_reminder_owner_required", "finance_reminder", type_="check")
    op.drop_constraint("finance_reminder_user_id_fkey", "finance_reminder", type_="foreignkey")
    op.drop_column("finance_reminder", "user_id")
    op.alter_column("finance_reminder", "membership_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_finance_payment_user_received", table_name="finance_payment")
    op.drop_constraint("finance_payment_owner_required", "finance_payment", type_="check")
    op.drop_constraint("finance_payment_user_id_fkey", "finance_payment", type_="foreignkey")
    op.drop_column("finance_payment", "user_id")
    op.alter_column("finance_payment", "membership_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_finance_charge_user_status", table_name="finance_charge")
    op.drop_constraint("finance_charge_registration_key", "finance_charge", type_="unique")
    op.drop_constraint("finance_charge_event_ticket_registration_required", "finance_charge", type_="check")
    op.drop_constraint("finance_charge_owner_required", "finance_charge", type_="check")
    op.drop_constraint("finance_charge_kind_valid", "finance_charge", type_="check")
    op.create_check_constraint(
        "finance_charge_kind_valid", "finance_charge", "kind IN ('drink', 'membership')"
    )
    op.drop_constraint("finance_charge_registration_id_fkey", "finance_charge", type_="foreignkey")
    op.drop_constraint("finance_charge_user_id_fkey", "finance_charge", type_="foreignkey")
    op.drop_column("finance_charge", "registration_id")
    op.drop_column("finance_charge", "user_id")
    op.alter_column("finance_charge", "membership_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("uq_user_role_request_pending", table_name="user_role_request")
    op.drop_index("ix_user_role_request_status", table_name="user_role_request")
    op.drop_table("user_role_request")
    op.drop_column("roles", "requestable_on_change")
