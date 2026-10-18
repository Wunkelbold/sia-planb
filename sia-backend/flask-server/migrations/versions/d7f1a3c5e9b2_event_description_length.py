"""Event description length

Revision ID: d7f1a3c5e9b2
Revises: e2b7c4a9d3f1
Create Date: 2026-10-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7f1a3c5e9b2"
down_revision = "e2b7c4a9d3f1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.alter_column(
            "description",
            existing_type=sa.String(length=300),
            type_=sa.String(length=2000),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.alter_column(
            "description",
            existing_type=sa.String(length=2000),
            type_=sa.String(length=300),
            existing_nullable=True,
        )
