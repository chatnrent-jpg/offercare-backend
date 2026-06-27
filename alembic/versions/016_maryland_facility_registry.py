"""Maryland facility registry — facilities, facility_contacts, md_provider_compliance."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision = "016_maryland_facility_registry"
down_revision = "015_maryland_market"
branch_labels = None
depends_on = None

FACILITY_TYPE = ENUM("SNF", "ALF", "HHA", name="facility_type_enum", create_type=False)
CONTACT_ROLE = ENUM("ADMINISTRATOR", "DON", "HR_HEAD", name="facility_contact_role_enum", create_type=False)
OUTREACH_STATUS = ENUM(
    "PENDING", "READY", "CONTACTED", "RESPONDED", "OPT_OUT", "BOUNCED",
    name="outreach_status_enum", create_type=False,
)
CREDENTIAL_TYPE = ENUM("CNA", "GNA", "LPN", name="md_credential_type_enum", create_type=False)
COMPLIANCE_STATUS = ENUM(
    "PENDING", "COMPLIANT", "NON_COMPLIANT", "EXPIRING", "REJECTED",
    name="md_compliance_status_enum", create_type=False,
)


def _ensure_enums() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE facility_type_enum AS ENUM ('SNF', 'ALF', 'HHA');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE facility_contact_role_enum AS ENUM ('ADMINISTRATOR', 'DON', 'HR_HEAD');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE outreach_status_enum AS ENUM (
                'PENDING', 'READY', 'CONTACTED', 'RESPONDED', 'OPT_OUT', 'BOUNCED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE md_credential_type_enum AS ENUM ('CNA', 'GNA', 'LPN');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE md_compliance_status_enum AS ENUM (
                'PENDING', 'COMPLIANT', 'NON_COMPLIANT', 'EXPIRING', 'REJECTED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    _ensure_enums()

    if "facilities" not in tables:
        op.create_table(
            "facilities",
            sa.Column("facility_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("facility_type", FACILITY_TYPE, nullable=False),
            sa.Column("md_license_number", sa.String(length=64), nullable=True),
            sa.Column("md_license_status", sa.String(length=40), nullable=False, server_default="UNKNOWN"),
            sa.Column("md_county", sa.String(length=100), nullable=False),
            sa.Column("state", sa.String(length=2), nullable=False, server_default="MD"),
            sa.Column("address_line", sa.String(length=255), nullable=True),
            sa.Column("city", sa.String(length=100), nullable=True),
            sa.Column("zip_code", sa.String(length=20), nullable=True),
            sa.Column("phone", sa.String(length=30), nullable=True),
            sa.Column(
                "maryland_facility_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_facilities.facility_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("source", sa.String(length=40), nullable=False, server_default="ohcq"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("md_license_number", name="uq_facilities_md_license"),
        )
        op.create_index("ix_facilities_md_county", "facilities", ["md_county"])
        op.create_index("ix_facilities_facility_type", "facilities", ["facility_type"])

    if "facility_contacts" not in tables:
        op.create_table(
            "facility_contacts",
            sa.Column("contact_id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "facility_id",
                UUID(as_uuid=True),
                sa.ForeignKey("facilities.facility_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("contact_role", CONTACT_ROLE, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=30), nullable=True),
            sa.Column("outreach_status", OUTREACH_STATUS, nullable=False, server_default="PENDING"),
            sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("facility_id", "email", name="uq_facility_contact_email"),
        )
        op.create_index("ix_facility_contacts_outreach_status", "facility_contacts", ["outreach_status"])
        op.create_index("ix_facility_contacts_role", "facility_contacts", ["contact_role"])
        op.create_index("ix_facility_contacts_facility_id", "facility_contacts", ["facility_id"])

    if "md_provider_compliance" not in tables:
        op.create_table(
            "md_provider_compliance",
            sa.Column("compliance_id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "provider_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_providers.provider_id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("credential_type", CREDENTIAL_TYPE, nullable=False),
            sa.Column("license_number", sa.String(length=50), nullable=False),
            sa.Column("has_gna_endorsement", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("license_expires_on", sa.DateTime(timezone=True), nullable=True),
            sa.Column("compliance_status", COMPLIANCE_STATUS, nullable=False, server_default="PENDING"),
            sa.Column("mbon_status_last_checked", sa.DateTime(timezone=True), nullable=True),
            sa.Column("mbon_last_status", sa.String(length=40), nullable=True),
            sa.Column("ohcq_sanction_flag", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("compact_multistate", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("home_county", sa.String(length=100), nullable=True),
            sa.Column("verification_payload_json", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.String(length=500), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_md_provider_compliance_home_county", "md_provider_compliance", ["home_county"])
        op.create_index("ix_md_provider_compliance_status", "md_provider_compliance", ["compliance_status"])
        op.create_index(
            "ix_md_provider_compliance_status_county",
            "md_provider_compliance",
            ["compliance_status", "home_county"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for table in ("md_provider_compliance", "facility_contacts", "facilities"):
        if table in tables:
            op.drop_table(table)
