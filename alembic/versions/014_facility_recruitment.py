"""Facility recruitment engine — contracts, B2B leads, VMS shift dedupe."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "014_facility_recruitment"
down_revision = "013_vettedcare_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "facility_contracts" not in tables:
        op.create_table(
            "facility_contracts",
            sa.Column("contract_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("facility_id", UUID(as_uuid=True), sa.ForeignKey("maryland_facilities.facility_id"), nullable=False),
            sa.Column("external_contract_id", sa.String(length=120), nullable=False),
            sa.Column("vms_source", sa.String(length=50), nullable=False, server_default="MSA_UPLOAD"),
            sa.Column("contract_name", sa.String(length=255), nullable=True),
            sa.Column("source_filename", sa.String(length=255), nullable=True),
            sa.Column("bill_rate_hourly", sa.Numeric(precision=8, scale=2), nullable=True),
            sa.Column("pay_rate_hourly", sa.Numeric(precision=8, scale=2), nullable=True),
            sa.Column("margin_dollars", sa.Numeric(precision=8, scale=2), nullable=True),
            sa.Column("margin_pct", sa.Numeric(precision=6, scale=4), nullable=True),
            sa.Column("cancellation_policy_text", sa.Text(), nullable=True),
            sa.Column("cancellation_notice_hours", sa.Numeric(precision=5, scale=0), nullable=True),
            sa.Column("credential_requirements_json", sa.Text(), nullable=True),
            sa.Column("review_status", sa.String(length=40), nullable=False, server_default="ACTIVE"),
            sa.Column("dispatch_halted", sa.String(length=5), nullable=False, server_default="false"),
            sa.Column("review_reason", sa.String(length=500), nullable=True),
            sa.Column("raw_text_excerpt", sa.Text(), nullable=True),
            sa.Column("parsed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.UniqueConstraint("facility_id", "external_contract_id", name="uq_facility_contract_external"),
        )
        op.create_index("ix_facility_contracts_facility_id", "facility_contracts", ["facility_id"])
        op.create_index("ix_facility_contracts_review_status", "facility_contracts", ["review_status"])

    if "b2b_raw_leads" not in tables:
        op.create_table(
            "b2b_raw_leads",
            sa.Column("lead_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("facility_name", sa.String(length=255), nullable=False),
            sa.Column("contact_role", sa.String(length=120), nullable=False),
            sa.Column("email_domain", sa.String(length=255), nullable=False),
            sa.Column("procurement_urgency", sa.String(length=50), nullable=False),
            sa.Column("source_url", sa.String(length=500), nullable=False),
            sa.Column("contact_name", sa.String(length=255), nullable=True),
            sa.Column("contact_email", sa.String(length=255), nullable=True),
            sa.Column("state", sa.String(length=2), nullable=False, server_default="MD"),
            sa.Column("county", sa.String(length=100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("manus_run_id", sa.String(length=128), nullable=True),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="manus"),
            sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )
        op.create_index("ix_b2b_raw_leads_facility", "b2b_raw_leads", ["facility_name"])
        op.create_index("ix_b2b_raw_leads_urgency", "b2b_raw_leads", ["procurement_urgency"])

    if "ingested_open_shifts" not in tables:
        op.create_table(
            "ingested_open_shifts",
            sa.Column("ingest_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("composite_hash", sa.String(length=64), nullable=False),
            sa.Column("facility_id", UUID(as_uuid=True), sa.ForeignKey("maryland_facilities.facility_id"), nullable=False),
            sa.Column("offer_id", UUID(as_uuid=True), sa.ForeignKey("offercare_job_offers.offer_id"), nullable=True),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="manus_vms"),
            sa.Column("shift_date", sa.String(length=20), nullable=False),
            sa.Column("unit_dept", sa.String(length=120), nullable=False),
            sa.Column("start_time", sa.String(length=20), nullable=False),
            sa.Column("shift_role", sa.String(length=100), nullable=False),
            sa.Column("hourly_pay_rate", sa.Numeric(precision=8, scale=2), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("match_payload_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="INGESTED"),
            sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.UniqueConstraint("composite_hash", name="uq_ingested_open_shift_hash"),
        )
        op.create_index("ix_ingested_open_shifts_facility", "ingested_open_shifts", ["facility_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for table in ("ingested_open_shifts", "b2b_raw_leads", "facility_contracts"):
        if table in tables:
            op.drop_table(table)
