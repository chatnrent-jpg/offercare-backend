"""Dual-account caregiver schema — MBON profile with Tier 1 W-2 and Tier 2 1099 structures."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision: str = "022_caregiver_dual_accounts"
down_revision: Union[str, None] = "021_clinician_oauth_identities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIER1 = "TIER1_W2"
_TIER2 = "TIER2_1099"
_EIN_STATUSES = ("UNVALIDATED", "PENDING", "VALIDATED", "REJECTED")


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _has_table(inspector, "caregiver_profiles"):
        op.create_table(
            "caregiver_profiles",
            sa.Column("caregiver_profile_id", UUID(as_uuid=True), primary_key=True),
            sa.Column("mbon_license_number", sa.String(length=50), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone_number", sa.String(length=20), nullable=True),
            sa.Column("credential_type", sa.String(length=20), nullable=False, server_default="CNA"),
            sa.Column(
                "employment_tier",
                sa.String(length=20),
                nullable=False,
                comment="TIER1_W2 for payroll employees; TIER2_1099 for independent contractors",
            ),
            sa.Column(
                "provider_id",
                UUID(as_uuid=True),
                sa.ForeignKey("maryland_providers.provider_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("account_status", sa.String(length=30), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("mbon_license_number", name="uq_caregiver_profiles_mbon_license"),
            sa.UniqueConstraint("provider_id", name="uq_caregiver_profiles_provider_id"),
            sa.CheckConstraint(
                f"employment_tier IN ('{_TIER1}', '{_TIER2}')",
                name="ck_caregiver_profiles_employment_tier",
            ),
        )
        op.create_index(
            "ix_caregiver_profiles_mbon_license_number",
            "caregiver_profiles",
            ["mbon_license_number"],
            unique=False,
        )

    inspector = inspect(bind)
    if not _has_table(inspector, "caregiver_w2_employee_accounts"):
        op.create_table(
            "caregiver_w2_employee_accounts",
            sa.Column("w2_account_id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "caregiver_profile_id",
                UUID(as_uuid=True),
                sa.ForeignKey("caregiver_profiles.caregiver_profile_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "maryland_residence_county",
                sa.String(length=100),
                nullable=False,
                comment="Maryland county of residence for localized income tax withholding",
            ),
            sa.Column(
                "local_tax_jurisdiction_code",
                sa.String(length=20),
                nullable=True,
                comment="Optional MD local tax jurisdiction code derived from residence county",
            ),
            sa.Column("w4_on_file", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "payroll_withholding_status",
                sa.String(length=30),
                nullable=False,
                server_default="PENDING_SETUP",
            ),
            sa.Column("employee_payroll_number", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("caregiver_profile_id", name="uq_caregiver_w2_profile"),
            sa.UniqueConstraint("employee_payroll_number", name="uq_caregiver_w2_payroll_number"),
        )
        op.create_index(
            "ix_caregiver_w2_maryland_residence_county",
            "caregiver_w2_employee_accounts",
            ["maryland_residence_county"],
            unique=False,
        )

    inspector = inspect(bind)
    if not _has_table(inspector, "caregiver_1099_contractor_accounts"):
        op.create_table(
            "caregiver_1099_contractor_accounts",
            sa.Column("contractor_account_id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "caregiver_profile_id",
                UUID(as_uuid=True),
                sa.ForeignKey("caregiver_profiles.caregiver_profile_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("corporate_legal_name", sa.String(length=255), nullable=False),
            sa.Column(
                "corporate_ein",
                sa.String(length=10),
                nullable=False,
                comment="Nine-digit IRS employer identification number (stored without hyphen)",
            ),
            sa.Column(
                "corporate_ein_validation_status",
                sa.String(length=30),
                nullable=False,
                server_default="UNVALIDATED",
            ),
            sa.Column("ein_validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ein_validation_reference", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("caregiver_profile_id", name="uq_caregiver_1099_profile"),
            sa.UniqueConstraint("corporate_ein", name="uq_caregiver_1099_corporate_ein"),
            sa.CheckConstraint(
                "corporate_ein ~ '^[0-9]{9}$'",
                name="ck_caregiver_1099_ein_format",
            ),
            sa.CheckConstraint(
                "corporate_ein_validation_status IN "
                f"({', '.join(repr(s) for s in _EIN_STATUSES)})",
                name="ck_caregiver_1099_ein_validation_status",
            ),
        )
        op.create_index(
            "ix_caregiver_1099_corporate_ein",
            "caregiver_1099_contractor_accounts",
            ["corporate_ein"],
            unique=False,
        )

    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION enforce_caregiver_tier_account_alignment()
            RETURNS trigger AS $$
            DECLARE
                tier text;
            BEGIN
                SELECT employment_tier INTO tier
                FROM caregiver_profiles
                WHERE caregiver_profile_id = NEW.caregiver_profile_id;

                IF tier IS NULL THEN
                    RAISE EXCEPTION 'caregiver_profile_id % not found', NEW.caregiver_profile_id;
                END IF;

                IF TG_TABLE_NAME = 'caregiver_w2_employee_accounts' AND tier <> '{_TIER1}' THEN
                    RAISE EXCEPTION 'W-2 account requires employment_tier {_TIER1}, got %', tier;
                END IF;

                IF TG_TABLE_NAME = 'caregiver_1099_contractor_accounts' AND tier <> '{_TIER2}' THEN
                    RAISE EXCEPTION '1099 account requires employment_tier {_TIER2}, got %', tier;
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_caregiver_w2_tier_alignment ON caregiver_w2_employee_accounts;
            CREATE TRIGGER trg_caregiver_w2_tier_alignment
            BEFORE INSERT OR UPDATE ON caregiver_w2_employee_accounts
            FOR EACH ROW EXECUTE FUNCTION enforce_caregiver_tier_account_alignment();
            """
        )
    )
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS trg_caregiver_1099_tier_alignment ON caregiver_1099_contractor_accounts;
            CREATE TRIGGER trg_caregiver_1099_tier_alignment
            BEFORE INSERT OR UPDATE ON caregiver_1099_contractor_accounts
            FOR EACH ROW EXECUTE FUNCTION enforce_caregiver_tier_account_alignment();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_caregiver_1099_tier_alignment ON caregiver_1099_contractor_accounts"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_caregiver_w2_tier_alignment ON caregiver_w2_employee_accounts"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS enforce_caregiver_tier_account_alignment()"))
    bind = op.get_bind()
    inspector = inspect(bind)
    if _has_table(inspector, "caregiver_1099_contractor_accounts"):
        op.drop_table("caregiver_1099_contractor_accounts")
    inspector = inspect(bind)
    if _has_table(inspector, "caregiver_w2_employee_accounts"):
        op.drop_table("caregiver_w2_employee_accounts")
    inspector = inspect(bind)
    if _has_table(inspector, "caregiver_profiles"):
        op.drop_table("caregiver_profiles")
