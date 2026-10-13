"""Add one shared handled state for contact requests."""

from alembic import op
import sqlalchemy as sa


revision = "b28d31f6a4c2"
down_revision = "f17c9a0e4b61"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contact", sa.Column("handled_at", sa.DateTime(), nullable=True))
    op.add_column("contact", sa.Column("handled_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "contact_handled_by_fkey", "contact", "user", ["handled_by"], ["id"], ondelete="SET NULL"
    )


def downgrade():
    op.drop_constraint("contact_handled_by_fkey", "contact", type_="foreignkey")
    op.drop_column("contact", "handled_by")
    op.drop_column("contact", "handled_at")
