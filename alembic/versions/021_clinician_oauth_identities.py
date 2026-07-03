"""Clinician OAuth identities for portal social sign-in."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "021_clinician_oauth_identities"
down_revision = "020_clinician_calendar_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "clinician_oauth_identities" in inspector.get_table_names():
        return
    op.create_table(
        "clinician_oauth_identities",
        sa.Column("identity_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("maryland_providers.provider_id"), nullable=False),
        sa.Column("oauth_provider", sa.String(length=32), nullable=False),
        sa.Column("oauth_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("oauth_provider", "oauth_subject", name="uq_clinician_oauth_provider_subject"),
    )


def downgrade() -> None:
    op.drop_table("clinician_oauth_identities")
