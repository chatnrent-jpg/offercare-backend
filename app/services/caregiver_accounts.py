"""Dual-account caregiver service — MBON profiles with Tier 1 W-2 and Tier 2 1099 accounts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    EIN_VALIDATION_PENDING,
    EIN_VALIDATION_REJECTED,
    EIN_VALIDATION_UNVALIDATED,
    EIN_VALIDATION_VALIDATED,
    EMPLOYMENT_TIER_1099,
    EMPLOYMENT_TIER_W2,
    EMPLOYMENT_TIERS,
    Caregiver1099ContractorAccount,
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
    MarylandProvider,
)
from app.services.skyflow_vault_service import (
    CaregiverPiiTokens,
    tokenize_caregiver_pii,
    tokens_to_profile_fields,
    tokens_to_w2_fields,
)
from app.services.maryland_facility_scraper import normalize_county

_EIN_DIGITS = re.compile(r"\D")


def normalize_corporate_ein(raw: str) -> str:
    """Normalize IRS EIN to nine digits (strip hyphens and non-numeric characters)."""
    digits = _EIN_DIGITS.sub("", str(raw or ""))
    if len(digits) != 9:
        raise ValueError("invalid_corporate_ein")
    return digits


def normalize_maryland_residence_county(raw: str) -> str:
    """Normalize Maryland county naming for localized withholding routing."""
    county = normalize_county(str(raw or "").strip())
    if not county:
        raise ValueError("maryland_residence_county_required")
    return county


def _normalize_mbon_license_number(raw: str) -> str:
    license_number = str(raw or "").strip().upper()
    if not license_number:
        raise ValueError("mbon_license_number_required")
    return license_number


def _validate_employment_tier(employment_tier: str) -> str:
    tier = str(employment_tier or "").strip().upper()
    if tier not in EMPLOYMENT_TIERS:
        raise ValueError("invalid_employment_tier")
    return tier


def tokenize_onboarding_pii_if_present(
    *,
    ssn: str | None = None,
    date_of_birth: str | None = None,
    stripe_routing_token: str | None = None,
) -> CaregiverPiiTokens | None:
    """Tokenize inbound onboarding PII via Skyflow before database persistence."""
    if not any(str(value or "").strip() for value in (ssn, date_of_birth, stripe_routing_token)):
        return None
    return tokenize_caregiver_pii(
        {
            "ssn": ssn,
            "date_of_birth": date_of_birth,
            "stripe_routing_token": stripe_routing_token,
        }
    )


def create_caregiver_profile(
    db: Session,
    *,
    mbon_license_number: str,
    full_name: str,
    employment_tier: str,
    credential_type: str = "CNA",
    email: str | None = None,
    phone_number: str | None = None,
    provider_id: UUID | None = None,
    account_status: str = "ACTIVE",
    pii_tokens: CaregiverPiiTokens | None = None,
    commit: bool = True,
) -> CaregiverProfile:
    token_fields = tokens_to_profile_fields(pii_tokens) if pii_tokens else {}
    profile = CaregiverProfile(
        mbon_license_number=_normalize_mbon_license_number(mbon_license_number),
        full_name=str(full_name).strip(),
        employment_tier=_validate_employment_tier(employment_tier),
        credential_type=str(credential_type or "CNA").strip().upper() or "CNA",
        email=str(email).strip().lower() if email else None,
        phone_number=str(phone_number).strip() if phone_number else None,
        provider_id=provider_id,
        account_status=str(account_status or "ACTIVE").strip().upper() or "ACTIVE",
        skyflow_vault_record_id=token_fields.get("skyflow_vault_record_id"),
        skyflow_ssn_token=token_fields.get("skyflow_ssn_token"),
        skyflow_dob_token=token_fields.get("skyflow_dob_token"),
    )
    db.add(profile)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("caregiver_profile_conflict") from exc
    db.refresh(profile)
    return profile


def create_w2_employee_account(
    db: Session,
    caregiver_profile_id: UUID,
    *,
    maryland_residence_county: str,
    local_tax_jurisdiction_code: str | None = None,
    w4_on_file: bool = False,
    payroll_withholding_status: str = "PENDING_SETUP",
    employee_payroll_number: str | None = None,
    pii_tokens: CaregiverPiiTokens | None = None,
    commit: bool = True,
) -> CaregiverW2EmployeeAccount:
    profile = get_caregiver_profile(db, caregiver_profile_id)
    if profile is None:
        raise ValueError("caregiver_profile_not_found")
    if profile.employment_tier != EMPLOYMENT_TIER_W2:
        raise ValueError("employment_tier_mismatch")

    w2_token_fields = tokens_to_w2_fields(pii_tokens) if pii_tokens else {}
    account = CaregiverW2EmployeeAccount(
        caregiver_profile_id=caregiver_profile_id,
        maryland_residence_county=normalize_maryland_residence_county(maryland_residence_county),
        local_tax_jurisdiction_code=(
            str(local_tax_jurisdiction_code).strip().upper()
            if local_tax_jurisdiction_code
            else None
        ),
        w4_on_file=bool(w4_on_file),
        payroll_withholding_status=str(payroll_withholding_status or "PENDING_SETUP").strip().upper(),
        employee_payroll_number=(
            str(employee_payroll_number).strip() if employee_payroll_number else None
        ),
        skyflow_stripe_routing_token=w2_token_fields.get("skyflow_stripe_routing_token"),
    )
    db.add(account)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("w2_account_conflict") from exc
    db.refresh(account)
    return account


def create_1099_contractor_account(
    db: Session,
    caregiver_profile_id: UUID,
    *,
    corporate_legal_name: str,
    corporate_ein: str,
    corporate_ein_validation_status: str = EIN_VALIDATION_UNVALIDATED,
    commit: bool = True,
) -> Caregiver1099ContractorAccount:
    profile = get_caregiver_profile(db, caregiver_profile_id)
    if profile is None:
        raise ValueError("caregiver_profile_not_found")
    if profile.employment_tier != EMPLOYMENT_TIER_1099:
        raise ValueError("employment_tier_mismatch")

    legal_name = str(corporate_legal_name or "").strip()
    if not legal_name:
        raise ValueError("corporate_legal_name_required")

    status = str(corporate_ein_validation_status or EIN_VALIDATION_UNVALIDATED).strip().upper()
    if status not in {
        EIN_VALIDATION_UNVALIDATED,
        EIN_VALIDATION_PENDING,
        EIN_VALIDATION_VALIDATED,
        EIN_VALIDATION_REJECTED,
    }:
        raise ValueError("invalid_ein_validation_status")

    account = Caregiver1099ContractorAccount(
        caregiver_profile_id=caregiver_profile_id,
        corporate_legal_name=legal_name,
        corporate_ein=normalize_corporate_ein(corporate_ein),
        corporate_ein_validation_status=status,
    )
    db.add(account)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("contractor_account_conflict") from exc
    db.refresh(account)
    return account


def get_caregiver_profile(db: Session, caregiver_profile_id: UUID) -> CaregiverProfile | None:
    return (
        db.query(CaregiverProfile)
        .filter(CaregiverProfile.caregiver_profile_id == caregiver_profile_id)
        .first()
    )


def get_caregiver_profile_by_mbon(db: Session, mbon_license_number: str) -> CaregiverProfile | None:
    normalized = _normalize_mbon_license_number(mbon_license_number)
    return (
        db.query(CaregiverProfile)
        .filter(CaregiverProfile.mbon_license_number == normalized)
        .first()
    )


def get_w2_employee_account(
    db: Session,
    caregiver_profile_id: UUID,
) -> CaregiverW2EmployeeAccount | None:
    return (
        db.query(CaregiverW2EmployeeAccount)
        .filter(CaregiverW2EmployeeAccount.caregiver_profile_id == caregiver_profile_id)
        .first()
    )


def get_1099_contractor_account(
    db: Session,
    caregiver_profile_id: UUID,
) -> Caregiver1099ContractorAccount | None:
    return (
        db.query(Caregiver1099ContractorAccount)
        .filter(Caregiver1099ContractorAccount.caregiver_profile_id == caregiver_profile_id)
        .first()
    )


def get_caregiver_account_bundle(db: Session, caregiver_profile_id: UUID) -> dict[str, Any]:
    profile = get_caregiver_profile(db, caregiver_profile_id)
    if profile is None:
        raise ValueError("caregiver_profile_not_found")

    tier_account: CaregiverW2EmployeeAccount | Caregiver1099ContractorAccount | None
    if profile.employment_tier == EMPLOYMENT_TIER_W2:
        tier_account = get_w2_employee_account(db, caregiver_profile_id)
    elif profile.employment_tier == EMPLOYMENT_TIER_1099:
        tier_account = get_1099_contractor_account(db, caregiver_profile_id)
    else:
        tier_account = None

    return {
        "profile": profile,
        "employment_tier": profile.employment_tier,
        "tier_account": tier_account,
    }


def link_caregiver_profile_to_provider(
    db: Session,
    caregiver_profile_id: UUID,
    provider_id: UUID,
    *,
    commit: bool = True,
) -> CaregiverProfile:
    profile = get_caregiver_profile(db, caregiver_profile_id)
    if profile is None:
        raise ValueError("caregiver_profile_not_found")
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    profile.provider_id = provider_id
    if not profile.email:
        profile.email = provider.email
    if not profile.phone_number:
        profile.phone_number = provider.phone_number
    if profile.mbon_license_number != str(provider.md_license_number).strip().upper():
        raise ValueError("mbon_license_mismatch")

    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("provider_link_conflict") from exc
    db.refresh(profile)
    return profile


def record_ein_validation(
    db: Session,
    contractor_account_id: UUID,
    *,
    status: str,
    validation_reference: str | None = None,
    validated_at: datetime | None = None,
    commit: bool = True,
) -> Caregiver1099ContractorAccount:
    account = (
        db.query(Caregiver1099ContractorAccount)
        .filter(Caregiver1099ContractorAccount.contractor_account_id == contractor_account_id)
        .first()
    )
    if account is None:
        raise ValueError("contractor_account_not_found")

    normalized_status = str(status or "").strip().upper()
    if normalized_status not in {
        EIN_VALIDATION_UNVALIDATED,
        EIN_VALIDATION_PENDING,
        EIN_VALIDATION_VALIDATED,
        EIN_VALIDATION_REJECTED,
    }:
        raise ValueError("invalid_ein_validation_status")

    account.corporate_ein_validation_status = normalized_status
    account.ein_validation_reference = (
        str(validation_reference).strip() if validation_reference else None
    )
    if normalized_status == EIN_VALIDATION_VALIDATED:
        account.ein_validated_at = validated_at or datetime.now(timezone.utc)
    elif normalized_status in {EIN_VALIDATION_UNVALIDATED, EIN_VALIDATION_PENDING, EIN_VALIDATION_REJECTED}:
        account.ein_validated_at = None

    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("ein_validation_update_failed") from exc
    db.refresh(account)
    return account


def provision_caregiver_from_provider(
    db: Session,
    provider: MarylandProvider,
    *,
    employment_tier: str,
    maryland_residence_county: str | None = None,
    local_tax_jurisdiction_code: str | None = None,
    corporate_legal_name: str | None = None,
    corporate_ein: str | None = None,
    ssn: str | None = None,
    date_of_birth: str | None = None,
    stripe_routing_token: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Create caregiver profile + tier account from an existing Maryland provider row."""
    tier = _validate_employment_tier(employment_tier)
    pii_tokens = tokenize_onboarding_pii_if_present(
        ssn=ssn,
        date_of_birth=date_of_birth,
        stripe_routing_token=stripe_routing_token,
    )
    profile = create_caregiver_profile(
        db,
        mbon_license_number=provider.md_license_number,
        full_name=provider.full_name,
        employment_tier=tier,
        credential_type=provider.credential_type,
        email=provider.email,
        phone_number=provider.phone_number,
        provider_id=provider.provider_id,
        pii_tokens=pii_tokens,
        commit=False,
    )

    tier_account: CaregiverW2EmployeeAccount | Caregiver1099ContractorAccount
    if tier == EMPLOYMENT_TIER_W2:
        if not maryland_residence_county:
            raise ValueError("maryland_residence_county_required")
        tier_account = create_w2_employee_account(
            db,
            profile.caregiver_profile_id,
            maryland_residence_county=maryland_residence_county,
            local_tax_jurisdiction_code=local_tax_jurisdiction_code,
            pii_tokens=pii_tokens,
            commit=False,
        )
    else:
        if not corporate_legal_name or not corporate_ein:
            raise ValueError("corporate_identity_required")
        tier_account = create_1099_contractor_account(
            db,
            profile.caregiver_profile_id,
            corporate_legal_name=corporate_legal_name,
            corporate_ein=corporate_ein,
            commit=False,
        )

    if commit:
        db.commit()
        db.refresh(profile)
        db.refresh(tier_account)
    else:
        db.flush()

    return {
        "profile": profile,
        "employment_tier": tier,
        "tier_account": tier_account,
    }
