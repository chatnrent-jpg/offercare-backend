"""Alembic migration for B2B outreach contacts and email log."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "010_outreach_pipeline"
down_revision: Union[str, None] = "009_vms_shift_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "facility_outreach_contacts" not in inspector.get_table_names():
        op.create_table(
            "facility_outreach_contacts",
            sa.Column("contact_id", sa.UUID(), nullable=False),
            sa.Column("facility_id", sa.UUID(), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("enriched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["facility_id"], ["maryland_facilities.facility_id"]),
            sa.PrimaryKeyConstraint("contact_id"),
            sa.UniqueConstraint("facility_id", "email", name="uq_outreach_contact_facility_email"),
        )
    inspector = inspect(bind)
    if "outreach_email_log" not in inspector.get_table_names():
        op.create_table(
            "outreach_email_log",
            sa.Column("email_id", sa.UUID(), nullable=False),
            sa.Column("facility_id", sa.UUID(), nullable=False),
            sa.Column("contact_id", sa.UUID(), nullable=True),
            sa.Column("recipient_name", sa.String(length=255), nullable=False),
            sa.Column("recipient_email", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("mode", sa.String(length=30), nullable=False),
            sa.Column("crisis_context", sa.String(length=500), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["contact_id"], ["facility_outreach_contacts.contact_id"]),
            sa.ForeignKeyConstraint(["facility_id"], ["maryland_facilities.facility_id"]),
            sa.PrimaryKeyConstraint("email_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table in ("outreach_email_log", "facility_outreach_contacts"):
        if table in inspector.get_table_names():
            op.drop_table(table)
