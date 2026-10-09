"""Create the schema that existed before the first tracked delta."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("permissions", sa.ARRAY(sa.TEXT()), nullable=False),
        sa.Column("selectable_on_register", sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint("name", name="roles_pkey"),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("surname", sa.String(length=20), nullable=True),
        sa.Column("lastname", sa.String(length=20), nullable=True),
        sa.Column("street", sa.String(length=25), nullable=True),
        sa.Column("street_no", sa.String(length=10), nullable=True),
        sa.Column("password", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=30), nullable=True),
        sa.Column("email_confirmed", sa.Boolean(), nullable=False),
        sa.Column("email_confirm_token", sa.String(length=64), nullable=True),
        sa.Column("email_cooldown", sa.TEXT(), nullable=True),
        sa.Column("hs_email", sa.String(length=30), nullable=True),
        sa.Column("hs_email_confirmed", sa.Boolean(), nullable=False),
        sa.Column("hs_email_confirm_token", sa.String(length=64), nullable=True),
        sa.Column("hs_email_cooldown", sa.TEXT(), nullable=True),
        sa.Column("city", sa.String(length=25), nullable=True),
        sa.Column("postalcode", sa.String(length=25), nullable=True),
        sa.Column("register_date", sa.TEXT(), nullable=True),
        sa.Column("last_login", sa.TEXT(), nullable=True),
        sa.Column("role", sa.TEXT(), nullable=False),
        sa.Column("permissions", sa.ARRAY(sa.TEXT()), nullable=False),
        sa.Column("last_updated", sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(
            ["role"], ["roles.name"], name="user_role_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="user_pkey"),
        sa.UniqueConstraint("uid", name="user_uid_key"),
        sa.UniqueConstraint("username", name="user_username_key"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=True),
        sa.Column("place", sa.String(length=50), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("postername", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["author"], ["user.id"], name="events_author_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="events_pkey"),
        sa.UniqueConstraint("uid", name="events_uid_key"),
    )

    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user", sa.Integer(), nullable=True),
        sa.Column("event", sa.Integer(), nullable=False),
        sa.Column("type", sa.TEXT(), nullable=False),
        sa.Column("start", sa.DateTime(), nullable=False),
        sa.Column("end", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event"], ["events.id"], name="shifts_event_fkey"
        ),
        sa.ForeignKeyConstraint(["user"], ["user.id"], name="shifts_user_fkey"),
        sa.PrimaryKeyConstraint("id", name="shifts_pkey"),
    )

    op.create_table(
        "contact",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=True),
        sa.Column("surname", sa.String(length=20), nullable=True),
        sa.Column("lastname", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=30), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created", sa.TEXT(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="contact_pkey"),
        sa.UniqueConstraint("uid", name="contact_uid_key"),
    )


def downgrade():
    op.drop_table("contact")
    op.drop_table("shifts")
    op.drop_table("events")
    op.drop_table("user")
    op.drop_table("roles")
