"""Add membership finance, tally, payment, and review records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from uuid import UUID


revision = "a81d934c2b17"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "membership",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("fee_category", sa.String(length=20), server_default="student", nullable=False),
        sa.Column("member_since", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column("special_rate_cents", sa.Integer(), nullable=True),
        sa.Column("special_rate_valid_until", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'ended')", name="membership_status_valid"),
        sa.CheckConstraint("fee_category IN ('student', 'alumni', 'special')", name="membership_category_valid"),
        sa.CheckConstraint("special_rate_cents IS NULL OR special_rate_cents >= 0", name="membership_special_rate_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="membership_created_by_fkey"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="RESTRICT", name="membership_user_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="membership_pkey"),
        sa.UniqueConstraint("uid", name="membership_uid_key"),
        sa.UniqueConstraint("user_id", name="membership_user_id_key"),
    )
    op.create_index("ix_membership_status", "membership", ["status"])

    op.create_table(
        "membership_fee_rate",
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("annual_amount_cents", sa.Integer(), nullable=False),
        sa.Column("first_year_free", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("category IN ('student', 'alumni')", name="membership_fee_rate_category_valid"),
        sa.CheckConstraint("annual_amount_cents >= 0", name="membership_fee_rate_amount_nonnegative"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="membership_fee_rate_updated_by_fkey"),
        sa.PrimaryKeyConstraint("category", name="membership_fee_rate_pkey"),
    )
    op.bulk_insert(
        sa.table(
            "membership_fee_rate",
            sa.column("category", sa.String()),
            sa.column("annual_amount_cents", sa.Integer()),
            sa.column("first_year_free", sa.Boolean()),
        ),
        [
            {"category": "student", "annual_amount_cents": 2000, "first_year_free": True},
            {"category": "alumni", "annual_amount_cents": 5000, "first_year_free": True},
        ],
    )

    op.create_table(
        "membership_request",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=20), server_default="category", nullable=False),
        sa.Column("requested_category", sa.String(length=20), nullable=False),
        sa.Column("request_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.CheckConstraint("request_type IN ('join', 'category')", name="membership_request_type_valid"),
        sa.CheckConstraint("requested_category IN ('student', 'alumni', 'special')", name="membership_request_category_valid"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="membership_request_status_valid"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"], ondelete="SET NULL", name="membership_request_reviewed_by_fkey"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE", name="membership_request_user_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="membership_request_pkey"),
        sa.UniqueConstraint("uid", name="membership_request_uid_key"),
    )
    op.create_index("ix_membership_request_status", "membership_request", ["status", "submitted_at"])

    op.create_table(
        "membership_student_verification",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("cycle_year", sa.Integer(), nullable=False),
        sa.Column("email_snapshot", sa.String(length=255), nullable=False),
        sa.Column("requested_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"], ondelete="RESTRICT", name="membership_student_verification_membership_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="membership_student_verification_pkey"),
        sa.UniqueConstraint("membership_id", "cycle_year", name="membership_student_verification_cycle_key"),
    )

    op.create_table(
        "tally_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="tally_item_price_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="tally_item_created_by_fkey"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="tally_item_updated_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="tally_item_pkey"),
        sa.UniqueConstraint("name", name="tally_item_name_key"),
        sa.UniqueConstraint("uid", name="tally_item_uid_key"),
    )
    op.bulk_insert(
        sa.table(
            "tally_item",
            sa.column("uid", postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String()),
            sa.column("price_cents", sa.Integer()),
            sa.column("is_active", sa.Boolean()),
        ),
        [
            {"uid": UUID("c2b7918d-5994-4ed4-900a-000000000001"), "name": "Glasflaschen", "price_cents": None, "is_active": False},
            {"uid": UUID("c2b7918d-5994-4ed4-900a-000000000002"), "name": "Longdrinks", "price_cents": None, "is_active": False},
        ],
    )

    op.create_table(
        "finance_billing_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_year", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="finance_billing_run_created_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_billing_run_pkey"),
        sa.UniqueConstraint("cycle_year", name="finance_billing_run_cycle_year_key"),
    )

    op.create_table(
        "finance_charge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("billing_run_id", sa.Integer(), nullable=True),
        sa.Column("tally_item_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("fee_category_snapshot", sa.String(length=20), nullable=True),
        sa.Column("cycle_year", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("status_by", sa.Integer(), nullable=True),
        sa.Column("status_at", sa.DateTime(), nullable=True),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('drink', 'membership')", name="finance_charge_kind_valid"),
        sa.CheckConstraint("status IN ('open', 'paid', 'cancelled', 'waived')", name="finance_charge_status_valid"),
        sa.CheckConstraint("amount_cents >= 0", name="finance_charge_amount_nonnegative"),
        sa.CheckConstraint("quantity > 0", name="finance_charge_quantity_positive"),
        sa.ForeignKeyConstraint(["billing_run_id"], ["finance_billing_run.id"], ondelete="SET NULL", name="finance_charge_billing_run_id_fkey"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="finance_charge_created_by_fkey"),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"], ondelete="RESTRICT", name="finance_charge_membership_id_fkey"),
        sa.ForeignKeyConstraint(["status_by"], ["user.id"], ondelete="SET NULL", name="finance_charge_status_by_fkey"),
        sa.ForeignKeyConstraint(["tally_item_id"], ["tally_item.id"], ondelete="SET NULL", name="finance_charge_tally_item_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_charge_pkey"),
        sa.UniqueConstraint("uid", name="finance_charge_uid_key"),
        sa.UniqueConstraint("membership_id", "kind", "cycle_year", name="finance_charge_membership_cycle_key"),
    )
    op.create_index("ix_finance_charge_member_status", "finance_charge", ["membership_id", "status", "created_at"])
    op.create_index("ix_finance_charge_billing_run", "finance_charge", ["billing_run_id"])

    op.create_table(
        "finance_payment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("voided_by", sa.Integer(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("amount_cents > 0", name="finance_payment_amount_positive"),
        sa.CheckConstraint("method IN ('bank_transfer', 'cash', 'other')", name="finance_payment_method_valid"),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"], ondelete="RESTRICT", name="finance_payment_membership_id_fkey"),
        sa.ForeignKeyConstraint(["recorded_by"], ["user.id"], ondelete="SET NULL", name="finance_payment_recorded_by_fkey"),
        sa.ForeignKeyConstraint(["voided_by"], ["user.id"], ondelete="SET NULL", name="finance_payment_voided_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_payment_pkey"),
        sa.UniqueConstraint("uid", name="finance_payment_uid_key"),
    )
    op.create_index("ix_finance_payment_membership_received", "finance_payment", ["membership_id", "received_at"])

    op.create_table(
        "finance_charge_status_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("charge_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL", name="finance_charge_status_history_changed_by_fkey"),
        sa.ForeignKeyConstraint(["charge_id"], ["finance_charge.id"], ondelete="CASCADE", name="finance_charge_status_history_charge_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_charge_status_history_pkey"),
    )
    op.create_index("ix_finance_charge_status_history_charge", "finance_charge_status_history", ["charge_id", "changed_at"])

    op.create_table(
        "finance_reminder",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("email_snapshot", sa.String(length=255), nullable=False),
        sa.Column("balance_snapshot_cents", sa.Integer(), nullable=False),
        sa.Column("sent_by", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"], ondelete="RESTRICT", name="finance_reminder_membership_id_fkey"),
        sa.ForeignKeyConstraint(["sent_by"], ["user.id"], ondelete="SET NULL", name="finance_reminder_sent_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_reminder_pkey"),
    )
    op.create_index("ix_finance_reminder_batch", "finance_reminder", ["batch_uid"])

    op.create_table(
        "finance_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_instructions", sa.Text(), server_default="", nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="finance_settings_updated_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_settings_pkey"),
    )
    op.bulk_insert(
        sa.table("finance_settings", sa.column("id", sa.Integer()), sa.column("payment_instructions", sa.Text())),
        [{"id": 1, "payment_instructions": ""}],
    )


def downgrade():
    op.drop_table("finance_settings")
    op.drop_index("ix_finance_reminder_batch", table_name="finance_reminder")
    op.drop_table("finance_reminder")
    op.drop_index("ix_finance_payment_membership_received", table_name="finance_payment")
    op.drop_table("finance_payment")
    op.drop_index("ix_finance_charge_status_history_charge", table_name="finance_charge_status_history")
    op.drop_table("finance_charge_status_history")
    op.drop_index("ix_finance_charge_billing_run", table_name="finance_charge")
    op.drop_index("ix_finance_charge_member_status", table_name="finance_charge")
    op.drop_table("finance_charge")
    op.drop_table("finance_billing_run")
    op.drop_table("tally_item")
    op.drop_table("membership_student_verification")
    op.drop_index("ix_membership_request_status", table_name="membership_request")
    op.drop_table("membership_request")
    op.drop_table("membership_fee_rate")
    op.drop_index("ix_membership_status", table_name="membership")
    op.drop_table("membership")
