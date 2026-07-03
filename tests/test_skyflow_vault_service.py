from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    CaregiverProfile,
    CaregiverW2EmployeeAccount,
    EMPLOYMENT_TIER_W2,
    MarylandProvider,
)
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.caregiver_accounts import (
    create_caregiver_profile,
    create_w2_employee_account,
    provision_caregiver_from_provider,
    tokenize_onboarding_pii_if_present,
)
from app.services.skyflow_vault_service import (
    detokenize_caregiver_pii,
    strip_cleartext_pii_from_payload,
    tokenize_caregiver_pii,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_tokenize_and_detokenize_roundtrip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_path = tmp_path / "skyflow_dry_vault.json"
    monkeypatch.setattr("app.services.skyflow_vault_service.settings.SKYFLOW_VAULT_DRY_RUN", True)
    monkeypatch.setattr("app.services.skyflow_vault_service.settings.SKYFLOW_VAULT_ENABLED", True)
    monkeypatch.setattr("app.services.skyflow_vault_service.settings.SKYFLOW_DRY_VAULT_PATH", str(vault_path))

    tokens = tokenize_caregiver_pii(
        {
            "ssn": "123-45-6789",
            "date_of_birth": "1990-03-15",
            "stripe_routing_token": "tok_abc123456789",
        }
    )
    assert tokens.ssn_token
    assert tokens.dob_token
    assert tokens.stripe_routing_token
    assert tokens.tokenization_mode == "dry_run"

    cleartext = detokenize_caregiver_pii(tokens)
    assert cleartext.ssn == "123456789"
    assert cleartext.date_of_birth == "1990-03-15"
    assert cleartext.stripe_routing_token == "tok_abc123456789"


def test_strip_cleartext_pii_from_payload() -> None:
    sanitized = strip_cleartext_pii_from_payload(
        {
            "full_name": "Jane Doe",
            "ssn": "123456789",
            "dob": "1990-01-01",
            "stripe_routing_token": "tok_test",
        }
    )
    assert "ssn" not in sanitized
    assert "dob" not in sanitized
    assert sanitized["full_name"] == "Jane Doe"


def test_provision_stores_skyflow_tokens_not_cleartext(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_path = tmp_path / "skyflow_dry_vault.json"
    monkeypatch.setattr("app.services.skyflow_vault_service.settings.SKYFLOW_VAULT_DRY_RUN", True)
    monkeypatch.setattr("app.services.skyflow_vault_service.settings.SKYFLOW_VAULT_ENABLED", True)
    monkeypatch.setattr("app.services.skyflow_vault_service.settings.SKYFLOW_DRY_VAULT_PATH", str(vault_path))

    token = uuid4().hex[:8].upper()
    license_number = f"CNASKY{token}"
    email = f"skyflow.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=f"Skyflow Test {token}",
        email=email,
        phone_number=f"410555{int(token[:4], 16) % 10000:04d}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=license_number,
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=25.0,
    )
    db.add(provider)
    db.flush()

    bundle = provision_caregiver_from_provider(
        db,
        provider,
        employment_tier=EMPLOYMENT_TIER_W2,
        maryland_residence_county="Baltimore City",
        ssn="987-65-4321",
        date_of_birth="1985-07-04",
        stripe_routing_token="tok_stripe987654",
        commit=False,
    )
    profile = bundle["profile"]
    w2 = bundle["tier_account"]

    assert profile.skyflow_ssn_token
    assert profile.skyflow_dob_token
    assert w2.skyflow_stripe_routing_token
    assert "987654321" not in json.dumps(
        {
            "ssn_token": profile.skyflow_ssn_token,
            "dob_token": profile.skyflow_dob_token,
            "stripe": w2.skyflow_stripe_routing_token,
        }
    )

    db.query(CaregiverW2EmployeeAccount).filter(
        CaregiverW2EmployeeAccount.caregiver_profile_id == profile.caregiver_profile_id
    ).delete(synchronize_session=False)
    db.query(CaregiverProfile).filter(
        CaregiverProfile.caregiver_profile_id == profile.caregiver_profile_id
    ).delete(synchronize_session=False)
    db.flush()


def test_tokenize_onboarding_pii_if_present_returns_none_when_empty() -> None:
    assert tokenize_onboarding_pii_if_present() is None
