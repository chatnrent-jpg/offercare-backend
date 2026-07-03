from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Caregiver1099ContractorAccount,
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
    EMPLOYMENT_TIER_1099,
    EMPLOYMENT_TIER_W2,
    EIN_VALIDATION_VALIDATED,
    MarylandProvider,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.caregiver_accounts import (
    create_1099_contractor_account,
    create_caregiver_profile,
    create_w2_employee_account,
    get_caregiver_account_bundle,
    normalize_corporate_ein,
    normalize_maryland_residence_county,
    provision_caregiver_from_provider,
    record_ein_validation,
)


def _unique_phone() -> str:
    return f"+1{uuid4().int % 10**10:010d}"


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _create_provider(db: Session, *, license_suffix: str) -> MarylandProvider:
    token = uuid4().hex[:8].upper()
    license_number = f"CNA{license_suffix}{token}"
    email = f"caregiver.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=f"Caregiver {token}",
        email=email,
        phone_number=_unique_phone(),
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=license_number,
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=25.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _cleanup_caregiver(db: Session, profile_id) -> None:
    db.query(CaregiverW2EmployeeAccount).filter(
        CaregiverW2EmployeeAccount.caregiver_profile_id == profile_id
    ).delete(synchronize_session=False)
    db.query(Caregiver1099ContractorAccount).filter(
        Caregiver1099ContractorAccount.caregiver_profile_id == profile_id
    ).delete(synchronize_session=False)
    db.query(CaregiverProfile).filter(CaregiverProfile.caregiver_profile_id == profile_id).delete(
        synchronize_session=False
    )
    db.commit()


def test_normalize_corporate_ein() -> None:
    assert normalize_corporate_ein("12-3456789") == "123456789"
    with pytest.raises(ValueError, match="invalid_corporate_ein"):
        normalize_corporate_ein("12345")


def test_normalize_maryland_residence_county() -> None:
    assert normalize_maryland_residence_county("montgomery") == "Montgomery County"


def test_create_w2_caregiver_bundle(db: Session) -> None:
    profile = create_caregiver_profile(
        db,
        mbon_license_number="CNAW2TEST001",
        full_name="W2 Caregiver",
        employment_tier=EMPLOYMENT_TIER_W2,
    )
    try:
        account = create_w2_employee_account(
            db,
            profile.caregiver_profile_id,
            maryland_residence_county="Howard",
            local_tax_jurisdiction_code="MD24003",
        )
        bundle = get_caregiver_account_bundle(db, profile.caregiver_profile_id)
        assert bundle["employment_tier"] == EMPLOYMENT_TIER_W2
        assert bundle["tier_account"].w2_account_id == account.w2_account_id
        assert account.maryland_residence_county == "Howard County"
    finally:
        _cleanup_caregiver(db, profile.caregiver_profile_id)


def test_create_1099_caregiver_bundle(db: Session) -> None:
    profile = create_caregiver_profile(
        db,
        mbon_license_number="CNA1099TEST001",
        full_name="1099 Caregiver",
        employment_tier=EMPLOYMENT_TIER_1099,
    )
    try:
        account = create_1099_contractor_account(
            db,
            profile.caregiver_profile_id,
            corporate_legal_name="Care LLC",
            corporate_ein="98-7654321",
        )
        validated = record_ein_validation(
            db,
            account.contractor_account_id,
            status=EIN_VALIDATION_VALIDATED,
            validation_reference="IRS-TIN-MATCH-001",
        )
        assert validated.corporate_ein == "987654321"
        assert validated.corporate_ein_validation_status == EIN_VALIDATION_VALIDATED
        assert validated.ein_validation_reference == "IRS-TIN-MATCH-001"
        assert validated.ein_validated_at is not None
    finally:
        _cleanup_caregiver(db, profile.caregiver_profile_id)


def test_w2_account_rejects_1099_profile(db: Session) -> None:
    profile = create_caregiver_profile(
        db,
        mbon_license_number="CNA1099MISMATCH",
        full_name="Tier Mismatch",
        employment_tier=EMPLOYMENT_TIER_1099,
    )
    try:
        with pytest.raises(ValueError, match="employment_tier_mismatch"):
            create_w2_employee_account(
                db,
                profile.caregiver_profile_id,
                maryland_residence_county="Baltimore",
            )
    finally:
        _cleanup_caregiver(db, profile.caregiver_profile_id)


def test_provision_caregiver_from_provider_w2(db: Session) -> None:
    provider = _create_provider(db, license_suffix="PROVW2")
    bundle = provision_caregiver_from_provider(
        db,
        provider,
        employment_tier=EMPLOYMENT_TIER_W2,
        maryland_residence_county="Prince George's",
    )
    profile = bundle["profile"]
    try:
        assert profile.provider_id == provider.provider_id
        assert profile.mbon_license_number == provider.md_license_number.upper()
        assert bundle["tier_account"].maryland_residence_county == "Prince George's County"
    finally:
        _cleanup_caregiver(db, profile.caregiver_profile_id)
        db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider.provider_id).delete(
            synchronize_session=False
        )
        db.commit()
