from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
    EMPLOYMENT_TIER_W2,
    LicenseVerificationLog,
    MarylandProvider,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.mbon_verification import MbonVerificationResult
from app.services.payroll_onboarding_syncer import (
    PAYROLL_ONBOARDING_DRY_RUN,
    PAYROLL_ONBOARDING_VALIDATION_ERROR,
    PayrollValidationError,
    build_gusto_employee_payload,
    is_mbon_realtime_clear,
    sync_payroll_onboarding_after_mbon_clear,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _w2_provider(db: Session) -> tuple[MarylandProvider, CaregiverProfile, CaregiverW2EmployeeAccount]:
    token = uuid4().hex[:8].upper()
    email = f"payroll.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=f"Payroll Sync {token}",
        email=email,
        phone_number=f"410555{int(token[:4], 16) % 10000:04d}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"CNA-PAY-{token}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=25.0,
        home_zip="21201",
    )
    db.add(provider)
    db.flush()
    profile = CaregiverProfile(
        mbon_license_number=provider.md_license_number,
        full_name=provider.full_name,
        email=provider.email,
        phone_number=provider.phone_number,
        credential_type="CNA",
        employment_tier=EMPLOYMENT_TIER_W2,
        provider_id=provider.provider_id,
    )
    db.add(profile)
    db.flush()
    w2 = CaregiverW2EmployeeAccount(
        caregiver_profile_id=profile.caregiver_profile_id,
        maryland_residence_county="Baltimore City",
    )
    db.add(w2)
    db.flush()
    return provider, profile, w2


def test_is_mbon_realtime_clear_active_api() -> None:
    result = MbonVerificationResult(
        status="ACTIVE",
        license_number="CNA-1",
        expires_on=None,
        disciplinary_action=False,
        source="MBON_API",
        raw={},
    )
    assert is_mbon_realtime_clear(result) is True


def test_build_gusto_employee_payload_maps_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.GUSTO_COMPANY_ID", "company-uuid-123")
    db = SessionLocal()
    try:
        provider, profile, w2 = _w2_provider(db)
        payload = build_gusto_employee_payload(provider, profile, w2)
        assert payload["company_uuid"] == "company-uuid-123"
        assert payload["email"] == provider.email
        assert payload["metadata"]["mbon_license_number"] == profile.mbon_license_number
        assert payload["metadata"]["maryland_residence_county"] == "Baltimore City"
    finally:
        db.rollback()
        db.close()


def test_sync_records_gusto_employee_id_dry_run(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.PAYROLL_ONBOARDING_DRY_RUN", True)
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.PAYROLL_TAX_PROVIDER", "gusto")
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.GUSTO_COMPANY_ID", "company-uuid-123")

    provider, profile, w2 = _w2_provider(db)
    mbon = MbonVerificationResult(
        status="ACTIVE",
        license_number=provider.md_license_number,
        expires_on=None,
        disciplinary_action=False,
        source="MBON_DRY_RUN",
        raw={},
    )
    result = sync_payroll_onboarding_after_mbon_clear(
        db,
        provider,
        mbon_result=mbon,
        commit=False,
    )
    db.flush()
    db.refresh(w2)

    assert result.status == PAYROLL_ONBOARDING_DRY_RUN
    assert w2.gusto_employee_id
    assert w2.gusto_employee_id.startswith("dry_gusto_emp_")


def test_validation_error_fallback(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.PAYROLL_ONBOARDING_DRY_RUN", False)
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.PAYROLL_TAX_PROVIDER", "gusto")
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.GUSTO_COMPANY_ID", "company-uuid-123")
    monkeypatch.setattr("app.services.payroll_onboarding_syncer.settings.GUSTO_API_TOKEN", "token")

    provider, profile, w2 = _w2_provider(db)
    mbon = MbonVerificationResult(
        status="ACTIVE",
        license_number=provider.md_license_number,
        expires_on=None,
        disciplinary_action=False,
        source="MBON_API",
        raw={},
    )

    class FakeResponse:
        status_code = 422
        text = '{"errors":[{"message":"Invalid email"}]}'

        def json(self):
            return {"errors": [{"message": "Invalid email"}]}

    def _fake_execute(*_args, **_kwargs):
        raise PayrollValidationError(
            [{"message": "Invalid email"}],
            status_code=422,
            endpoint="http://test",
        )

    monkeypatch.setattr(
        "app.services.payroll_onboarding_syncer.execute_payroll_employee_create",
        _fake_execute,
    )

    result = sync_payroll_onboarding_after_mbon_clear(
        db,
        provider,
        mbon_result=mbon,
        commit=False,
    )
    db.flush()
    db.refresh(w2)

    assert result.status == PAYROLL_ONBOARDING_VALIDATION_ERROR
    assert w2.payroll_withholding_status == "PAYROLL_VALIDATION_ERROR"
    assert "Invalid email" in str(w2.payroll_onboarding_error)
    audit = (
        db.query(LicenseVerificationLog)
        .filter(
            LicenseVerificationLog.provider_id == provider.provider_id,
            LicenseVerificationLog.event_type == "PAYROLL_ONBOARDING_SYNC",
        )
        .first()
    )
    assert audit is not None
