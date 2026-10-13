"""Correct zero-value and pre-membership dues left open by the initial billing preview."""

from alembic import op


revision = "c317fd942a6b"
down_revision = "b92a4cf341df"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        WITH changed AS (
            UPDATE finance_charge AS charge
            SET status = 'cancelled',
                status_at = CURRENT_TIMESTAMP,
                status_note = 'Beitragsfälligkeit lag vor dem Mitgliedschaftsbeginn.'
            FROM membership
            WHERE charge.membership_id = membership.id
              AND charge.kind = 'membership'
              AND charge.status = 'open'
              AND charge.due_date IS NOT NULL
              AND charge.due_date < membership.member_since
            RETURNING charge.id
        )
        INSERT INTO finance_charge_status_history
            (charge_id, from_status, to_status, changed_by, changed_at, note)
        SELECT id, 'open', 'cancelled', NULL, CURRENT_TIMESTAMP,
               'Beitragsfälligkeit lag vor dem Mitgliedschaftsbeginn.'
        FROM changed
        """
    )
    op.execute(
        """
        WITH changed AS (
            UPDATE finance_charge
            SET status = 'waived',
                status_at = CURRENT_TIMESTAMP,
                status_note = 'Beitragsfreies erstes Mitgliedsjahr.'
            WHERE kind = 'membership'
              AND status = 'open'
              AND amount_cents = 0
            RETURNING id
        )
        INSERT INTO finance_charge_status_history
            (charge_id, from_status, to_status, changed_by, changed_at, note)
        SELECT id, 'open', 'waived', NULL, CURRENT_TIMESTAMP,
               'Beitragsfreies erstes Mitgliedsjahr.'
        FROM changed
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM finance_charge_status_history
        WHERE changed_by IS NULL
          AND note IN (
              'Beitragsfälligkeit lag vor dem Mitgliedschaftsbeginn.',
              'Beitragsfreies erstes Mitgliedsjahr.'
          )
        """
    )
    op.execute(
        """
        UPDATE finance_charge
        SET status = 'open', status_at = NULL, status_note = NULL
        WHERE status_note IN (
            'Beitragsfälligkeit lag vor dem Mitgliedschaftsbeginn.',
            'Beitragsfreies erstes Mitgliedsjahr.'
        )
        """
    )
