"""Add VettedMe.ai credential safety foundation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013_vettedme_foundation"
down_revision = "012_sms_opt_out"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "maryland_providers",
        sa.Column("vetted_status", sa.String(length=30), nullable=False, server_default="ACTION_NEEDED"),
    )
    op.add_column(
        "maryland_providers",
        sa.Column("vetted_status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "vettedme_audit_log",
        sa.Column("audit_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("maryland_providers.provider_id"), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "credential_safety_alerts",
        sa.Column("alert_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("maryland_providers.provider_id"), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column("vetted_status", sa.String(length=30), nullable=False),
        sa.Column("message_body", sa.String(length=1000), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "manus_vetting_runs",
        sa.Column("run_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("external_run_id", sa.String(length=128), nullable=True),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("maryland_providers.provider_id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RECEIVED"),
        sa.Column("checks_count", sa.Numeric(5, 0), nullable=False, server_default="0"),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("manus_vetting_runs")
    op.drop_table("credential_safety_alerts")
    op.drop_table("vettedme_audit_log")
    op.drop_column("maryland_providers", "vetted_status_updated_at")
    op.drop_column("maryland_providers", "vetted_status")
