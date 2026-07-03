"""Dual-account caregiver ORM — MBON profile with Tier 1 W-2 and Tier 2 1099 extensions."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base

EMPLOYMENT_TIER_W2 = "TIER1_W2"
EMPLOYMENT_TIER_1099 = "TIER2_1099"
EMPLOYMENT_TIERS = (EMPLOYMENT_TIER_W2, EMPLOYMENT_TIER_1099)

EIN_VALIDATION_UNVALIDATED = "UNVALIDATED"
EIN_VALIDATION_PENDING = "PENDING"
EIN_VALIDATION_VALIDATED = "VALIDATED"
EIN_VALIDATION_REJECTED = "REJECTED"
EIN_VALIDATION_STATUSES = (
    EIN_VALIDATION_UNVALIDATED,
    EIN_VALIDATION_PENDING,
    EIN_VALIDATION_VALIDATED,
    EIN_VALIDATION_REJECTED,
)


class CaregiverProfile(Base):
    """Primary caregiver identity keyed by MBON license number."""

    __tablename__ = "caregiver_profiles"
    __table_args__ = (
        CheckConstraint(
            f"employment_tier IN ('{EMPLOYMENT_TIER_W2}', '{EMPLOYMENT_TIER_1099}')",
            name="ck_caregiver_profiles_employment_tier",
        ),
    )

    caregiver_profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mbon_license_number = Column(String(50), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    credential_type = Column(String(20), nullable=False, default="CNA")
    employment_tier = Column(String(20), nullable=False)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maryland_providers.provider_id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    account_status = Column(String(30), nullable=False, default="ACTIVE")
    skyflow_vault_record_id = Column(String(128), nullable=True)
    skyflow_ssn_token = Column(String(128), nullable=True)
    skyflow_dob_token = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CaregiverW2EmployeeAccount(Base):
    """Tier 1 W-2 payroll account — Maryland county drives localized withholding."""

    __tablename__ = "caregiver_w2_employee_accounts"

    w2_account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caregiver_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("caregiver_profiles.caregiver_profile_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    maryland_residence_county = Column(String(100), nullable=False)
    local_tax_jurisdiction_code = Column(String(20), nullable=True)
    w4_on_file = Column(Boolean, nullable=False, default=False)
    payroll_withholding_status = Column(String(30), nullable=False, default="PENDING_SETUP")
    employee_payroll_number = Column(String(50), nullable=True, unique=True)
    gusto_employee_id = Column(String(128), nullable=True)
    payroll_onboarding_error = Column(String(2000), nullable=True)
    skyflow_stripe_routing_token = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Caregiver1099ContractorAccount(Base):
    """Tier 2 1099 contractor account — corporate EIN validation required."""

    __tablename__ = "caregiver_1099_contractor_accounts"
    __table_args__ = (
        CheckConstraint("corporate_ein ~ '^[0-9]{9}$'", name="ck_caregiver_1099_ein_format"),
        CheckConstraint(
            "corporate_ein_validation_status IN "
            f"({', '.join(repr(status) for status in EIN_VALIDATION_STATUSES)})",
            name="ck_caregiver_1099_ein_validation_status",
        ),
    )

    contractor_account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caregiver_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("caregiver_profiles.caregiver_profile_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    corporate_legal_name = Column(String(255), nullable=False)
    corporate_ein = Column(String(10), nullable=False, unique=True)
    corporate_ein_validation_status = Column(
        String(30),
        nullable=False,
        default=EIN_VALIDATION_UNVALIDATED,
    )
    ein_validated_at = Column(DateTime(timezone=True), nullable=True)
    ein_validation_reference = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


CaregiverProfileModel = CaregiverProfile
CaregiverW2EmployeeAccountModel = CaregiverW2EmployeeAccount
Caregiver1099ContractorAccountModel = Caregiver1099ContractorAccount
