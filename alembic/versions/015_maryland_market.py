"""Maryland LTC market — MBON licensure profile, B2B lead enrichment, outreach payloads."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "015_maryland_market"
down_revision = "014_facility_recruitment"
branch_labels = None
depends_on = None


def _column_names(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "md_provider_licensure" not in tables:
        op.create_table(
            "md_provider_licensure",
            sa.Column("profile_id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "provider_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("cna_license_number", sa.String(length=50), nullable=True),
            sa.Column("gna_endorsement_status", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("mbon_status_last_checked", sa.DateTime(timezone=True), nullable=True),
            sa.Column("mbon_last_status", sa.String(length=40), nullable=True),
            sa.Column("mbon_expires_on", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ohcq_sanction_flag", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("compact_multistate", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("facility_county", sa.String(length=100), nullable=True),
            sa.Column("verification_payload_json", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )
        op.create_index("ix_md_provider_licensure_county", "md_provider_licensure", ["facility_county"])
        op.create_index(
            "ix_md_provider_licensure_mbon_checked",
            "md_provider_licensure",
            ["mbon_status_last_checked"],
        )

    if "b2b_raw_leads" in tables:
        lead_cols = _column_names(inspector, "b2b_raw_leads")
        additions = {
            "facility_type": sa.Column("facility_type", sa.String(length=10), nullable=True),
            "md_license_status": sa.Column("md_license_status", sa.String(length=40), nullable=True),
            "decision_maker_name": sa.Column("decision_maker_name", sa.String(length=255), nullable=True),
            "decision_maker_title": sa.Column("decision_maker_title", sa.String(length=120), nullable=True),
            "direct_email": sa.Column("direct_email", sa.String(length=255), nullable=True),
            "facility_county": sa.Column("facility_county", sa.String(length=100), nullable=True),
            "outreach_payload_json": sa.Column("outreach_payload_json", sa.Text(), nullable=True),
            "outreach_ready": sa.Column(
                "outreach_ready",
                sa.String(length=5),
                nullable=False,
                server_default="false",
            ),
        }
        for name, col in additions.items():
            if name not in lead_cols:
                op.add_column("b2b_raw_leads", col)
        if "facility_type" not in lead_cols:
            op.create_index("ix_b2b_raw_leads_facility_type", "b2b_raw_leads", ["facility_type"])
        if "facility_county" not in lead_cols:
            op.create_index("ix_b2b_raw_leads_facility_county", "b2b_raw_leads", ["facility_county"])

    if "facility_contracts" in tables:
        contract_cols = _column_names(inspector, "facility_contracts")
        if "staffing_role" not in contract_cols:
            op.add_column("facility_contracts", sa.Column("staffing_role", sa.String(length=20), nullable=True))
        if "md_regional_bill_floor" not in contract_cols:
            op.add_column(
                "facility_contracts",
                sa.Column("md_regional_bill_floor", sa.Numeric(precision=8, scale=2), nullable=True),
            )

    if "md_outreach_payloads" not in tables:
        op.create_table(
            "md_outreach_payloads",
            sa.Column("payload_id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "lead_id",
                UUID(as_uuid=True),
                sa.ForeignKey("b2b_raw_leads.lead_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("facility_name", sa.String(length=255), nullable=False),
            sa.Column("decision_maker_name", sa.String(length=255), nullable=True),
            sa.Column("decision_maker_title", sa.String(length=120), nullable=True),
            sa.Column("direct_email", sa.String(length=255), nullable=True),
            sa.Column("facility_county", sa.String(length=100), nullable=True),
            sa.Column("facility_type", sa.String(length=10), nullable=True),
            sa.Column("email_subject", sa.String(length=500), nullable=False),
            sa.Column("email_body", sa.Text(), nullable=False),
            sa.Column("sms_body", sa.String(length=320), nullable=True),
            sa.Column("channel", sa.String(length=20), nullable=False, server_default="EMAIL"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="READY"),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )
        op.create_index("ix_md_outreach_payloads_status", "md_outreach_payloads", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "md_outreach_payloads" in tables:
        op.drop_table("md_outreach_payloads")

    if "facility_contracts" in tables:
        contract_cols = _column_names(inspector, "facility_contracts")
        if "md_regional_bill_floor" in contract_cols:
            op.drop_column("facility_contracts", "md_regional_bill_floor")
        if "staffing_role" in contract_cols:
            op.drop_column("facility_contracts", "staffing_role")

    if "b2b_raw_leads" in tables:
        lead_cols = _column_names(inspector, "b2b_raw_leads")
        for name in (
            "outreach_ready",
            "outreach_payload_json",
            "facility_county",
            "direct_email",
            "decision_maker_title",
            "decision_maker_name",
            "md_license_status",
            "facility_type",
        ):
            if name in lead_cols:
                op.drop_column("b2b_raw_leads", name)

    if "md_provider_licensure" in tables:
        op.drop_table("md_provider_licensure")
