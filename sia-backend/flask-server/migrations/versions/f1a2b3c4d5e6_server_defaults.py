"""Add database defaults required by SET DEFAULT foreign keys."""

from alembic import op


revision = "f1a2b3c4d5e6"
down_revision = "28b626b42cef"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE events ALTER COLUMN author SET DEFAULT 1")
    op.execute('ALTER TABLE task ALTER COLUMN "authorFK" SET DEFAULT 1')


def downgrade():
    op.execute("ALTER TABLE events ALTER COLUMN author DROP DEFAULT")
    op.execute('ALTER TABLE task ALTER COLUMN "authorFK" DROP DEFAULT')
