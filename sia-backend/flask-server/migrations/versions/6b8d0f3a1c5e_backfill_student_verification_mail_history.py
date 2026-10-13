"""Preserve the latest known student verification request in mail history."""

from alembic import op


revision = "6b8d0f3a1c5e"
down_revision = "5a7c9e1b2d4f"
branch_labels = None
depends_on = None


def upgrade():
    # The previous table stores only the latest request per member/year. Keep
    # that fact visible, while labeling it as an attempted send with unknown
    # delivery rather than claiming a complete per-send history.
    op.execute(
        """
        INSERT INTO finance_mail_campaign
            (uid, kind, source, cycle_year, test_only, subject_template,
             body_template, created_at, status)
        SELECT md5('legacy-student-verification:' || cycle_year::text)::uuid,
               'student_verification', 'legacy', cycle_year, false,
               'Studentenstatus für den Mitgliedsbeitrag bestätigen', '',
               MIN(requested_at), 'legacy'
        FROM membership_student_verification
        GROUP BY cycle_year
        ON CONFLICT (uid) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO finance_mail_recipient
            (campaign_id, recipient_key, user_id, membership_id, username_snapshot,
             display_name_snapshot, email_snapshot, status, attempted_at, completed_at)
        SELECT campaign.id, 'legacy-verification:' || verification.id::text,
               membership.user_id, membership.id, COALESCE(account.username, ''),
               COALESCE(NULLIF(CONCAT_WS(' ', account.surname, account.lastname), ''), account.username, ''),
               verification.email_snapshot, 'legacy_attempted',
               verification.requested_at, verification.requested_at
        FROM membership_student_verification AS verification
        JOIN membership ON membership.id = verification.membership_id
        JOIN "user" AS account ON account.id = membership.user_id
        JOIN finance_mail_campaign AS campaign
          ON campaign.kind = 'student_verification'
         AND campaign.source = 'legacy'
         AND campaign.cycle_year = verification.cycle_year
        ON CONFLICT (campaign_id, recipient_key) DO NOTHING
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM finance_mail_recipient
        WHERE recipient_key LIKE 'legacy-verification:%'
          AND campaign_id IN (
              SELECT id FROM finance_mail_campaign
              WHERE kind = 'student_verification' AND source = 'legacy'
          )
        """
    )
    op.execute(
        """
        DELETE FROM finance_mail_campaign
        WHERE kind = 'student_verification' AND source = 'legacy'
        """
    )
