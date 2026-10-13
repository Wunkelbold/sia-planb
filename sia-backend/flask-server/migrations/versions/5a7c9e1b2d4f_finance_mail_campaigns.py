"""Add shared finance mail drafts and campaign audit history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "5a7c9e1b2d4f"
down_revision = "b28d31f6a4c2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "finance_settings",
        sa.Column("mail_test_email", sa.String(length=255), server_default="", nullable=False),
    )
    op.create_table(
        "finance_mail_draft",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("subject_template", sa.String(length=255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("minimum_balance_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cycle_year", sa.Integer(), nullable=True),
        sa.Column("selected_recipient_keys", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('payment_reminder', 'student_verification')",
            name="finance_mail_draft_kind_valid",
        ),
        sa.CheckConstraint("minimum_balance_cents >= 0", name="finance_mail_draft_threshold_nonnegative"),
        sa.CheckConstraint("version > 0", name="finance_mail_draft_version_positive"),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL", name="finance_mail_draft_updated_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_mail_draft_pkey"),
        sa.UniqueConstraint("kind", name="finance_mail_draft_kind_key"),
    )
    op.create_table(
        "finance_mail_campaign",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="admin", nullable=False),
        sa.Column("cycle_year", sa.Integer(), nullable=True),
        sa.Column("minimum_balance_cents", sa.Integer(), nullable=True),
        sa.Column("test_only", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("subject_template", sa.String(length=255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="sending", nullable=False),
        sa.Column("counts", sa.JSON(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('payment_reminder', 'student_verification')",
            name="finance_mail_campaign_kind_valid",
        ),
        sa.CheckConstraint(
            "minimum_balance_cents IS NULL OR minimum_balance_cents >= 0",
            name="finance_mail_campaign_threshold_nonnegative",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL", name="finance_mail_campaign_created_by_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_mail_campaign_pkey"),
        sa.UniqueConstraint("uid", name="finance_mail_campaign_uid_key"),
    )
    op.create_index(
        "ix_finance_mail_campaign_kind_created",
        "finance_mail_campaign",
        ["kind", "created_at"],
    )
    op.create_table(
        "finance_mail_recipient",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("recipient_key", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("membership_id", sa.Integer(), nullable=True),
        sa.Column("username_snapshot", sa.String(length=80), server_default="", nullable=False),
        sa.Column("display_name_snapshot", sa.String(length=160), server_default="", nullable=False),
        sa.Column("email_snapshot", sa.String(length=255), nullable=True),
        sa.Column("balance_snapshot_cents", sa.Integer(), nullable=True),
        sa.Column("activity_snapshot", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("subject_snapshot", sa.String(length=255), nullable=True),
        sa.Column("body_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'accepted', 'failed', 'skipped', 'excluded', 'legacy_attempted')",
            name="finance_mail_recipient_status_valid",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["finance_mail_campaign.id"], ondelete="CASCADE", name="finance_mail_recipient_campaign_id_fkey"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL", name="finance_mail_recipient_user_id_fkey"),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"], ondelete="SET NULL", name="finance_mail_recipient_membership_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="finance_mail_recipient_pkey"),
        sa.UniqueConstraint("campaign_id", "recipient_key", name="finance_mail_recipient_campaign_key"),
    )
    op.create_index(
        "ix_finance_mail_recipient_campaign_status",
        "finance_mail_recipient",
        ["campaign_id", "status"],
    )

    # Preserve the existing reminder audit at the batch level. Its old rows only
    # prove that a mail thread was started, not that the destination received it.
    op.execute(
        """
        INSERT INTO finance_mail_campaign
            (uid, kind, source, minimum_balance_cents, test_only, subject_template,
             body_template, created_by, created_at, status)
        SELECT batch_uid, 'payment_reminder', 'legacy', 0, false,
               'Offener Finanzsaldo', '', MIN(sent_by), MIN(sent_at), 'legacy'
        FROM finance_reminder
        GROUP BY batch_uid
        ON CONFLICT (uid) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO finance_mail_recipient
            (campaign_id, recipient_key, user_id, membership_id, username_snapshot,
             display_name_snapshot, email_snapshot, balance_snapshot_cents, status,
             attempted_at, completed_at)
        SELECT campaign.id, 'legacy:' || reminder.id::text,
               COALESCE(reminder.user_id, membership.user_id), reminder.membership_id,
               COALESCE(account.username, ''),
               COALESCE(NULLIF(CONCAT_WS(' ', account.surname, account.lastname), ''), account.username, ''),
               reminder.email_snapshot, reminder.balance_snapshot_cents, 'legacy_attempted',
               reminder.sent_at, reminder.sent_at
        FROM finance_reminder AS reminder
        JOIN finance_mail_campaign AS campaign ON campaign.uid = reminder.batch_uid
        LEFT JOIN membership ON membership.id = reminder.membership_id
        LEFT JOIN "user" AS account ON account.id = COALESCE(reminder.user_id, membership.user_id)
        ON CONFLICT (campaign_id, recipient_key) DO NOTHING
        """
    )
def downgrade():
    op.drop_index("ix_finance_mail_recipient_campaign_status", table_name="finance_mail_recipient")
    op.drop_table("finance_mail_recipient")
    op.drop_index("ix_finance_mail_campaign_kind_created", table_name="finance_mail_campaign")
    op.drop_table("finance_mail_campaign")
    op.drop_table("finance_mail_draft")
    op.drop_column("finance_settings", "mail_test_email")
