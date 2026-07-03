from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.license_verification import (
    apply_as_clinician,
    is_valid_npi,
    list_pending_clinicians,
    run_license_auto_check,
    verify_clinician,
)
from app.schemas import ClinicianApplyRequest


def _make_valid_npi(seed: int) -> str:
    base9 = f"{seed % 1_000_000_000:09d}"
    for check in range(10):
        candidate = f"{base9}{check}"
        if is_valid_npi(candidate):
            return candidate
    raise ValueError("unable to build valid NPI")


def _apply_payload(**overrides) -> ClinicianApplyRequest:
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    suffix = seed % 10_000_000
    base = {
        "full_name": "Nurse Test",
        "email": f"nurse.{token}@offercare.demo",
        "phone_number": f"410{suffix:07d}",
        "npi_number": _make_valid_npi(seed),
        "md_license_number": f"RN-MD-{token.upper()}",
        "min_hourly_rate": 95.0,
        "response_propensity": 0.7,
        "fatigue_score": 0.0,
    }
    base.update(overrides)
    return ClinicianApplyRequest(**base)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_npi_checksum_validation() -> None:
    assert is_valid_npi("1234567893")
    assert not is_valid_npi("1234567890")


def test_auto_check_passes_valid_credentials() -> None:
    result = run_license_auto_check(npi_number="1234567893", md_license_number="RN-MD-T001")
    assert result.result == "STUB_PASS"


def test_auto_check_fails_invalid_npi() -> None:
    result = run_license_auto_check(npi_number="0000000000", md_license_number="RN-MD-T001")
    assert result.result == "FAIL"


def test_apply_creates_unverified_provider(db: Session) -> None:
    payload = _apply_payload()
    provider, auto_check = apply_as_clinician(db, payload)
    assert provider.license_status == "UNVERIFIED"
    assert auto_check.result == "STUB_PASS"
    assert provider.phone_number.startswith("+1")

    pending = list_pending_clinicians(db)
    assert any(row.provider_id == provider.provider_id for row in pending)


def test_verify_promotes_provider(db: Session) -> None:
    provider, _ = apply_as_clinician(db, _apply_payload())
    verified, log = verify_clinician(
        db,
        provider.provider_id,
        action="VERIFY",
        notes="Maryland board confirmed",
        reviewer="compliance_admin",
    )
    assert verified.license_status == "VERIFIED"
    assert verified.last_verified_timestamp is not None
    assert log.event_type == "VERIFIED"
    assert log.check_result == "MANUAL_APPROVED"


def test_reject_provider(db: Session) -> None:
    provider, _ = apply_as_clinician(db, _apply_payload())
    rejected, log = verify_clinician(
        db,
        provider.provider_id,
        action="REJECT",
        notes="License mismatch",
    )
    assert rejected.license_status == "REJECTED"
    assert log.event_type == "REJECTED"


from app.services.worker_consent import WORKER_CONSENT_VERSION


def test_legacy_clinician_apply_returns_410(client: TestClient) -> None:
    response = client.post(
        "/api/clinicians/apply",
        json={
            "full_name": "Legacy Nurse",
            "email": "legacy@example.com",
            "phone_number": "4105559999",
            "md_license_number": "RN-MD-LEGACY",
            "min_hourly_rate": 50.0,
        },
    )
    assert response.status_code == 410
    assert response.json()["detail"] == "use_join_landing"
    assert response.headers.get("x-apply-url") == "/join"


def test_api_apply_and_verify_flow(client: TestClient) -> None:
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    suffix = seed % 10_000_000
    email = f"api.{token}@offercare.demo"
    apply_resp = client.post(
        "/api/landing/maryland/apply",
        json={
            "full_name": "API Nurse",
            "email": email,
            "phone_number": f"410{suffix:07d}",
            "md_license_number": f"RN-MD-{token.upper()}",
            "credential_type": "CNA",
            "min_hourly_rate": 100.0,
            "password": "testpass123",
            "consent_version": WORKER_CONSENT_VERSION,
            "consent_credential_screening": True,
            "consent_sms_dispatch": True,
            "consent_privacy_policy": True,
            "consent_terms_of_service": True,
            "consent_aedt_30_day": True,
        },
    )
    assert apply_resp.status_code == 200
    body = apply_resp.json()
    assert body["license_status"] in {"UNVERIFIED", "VERIFIED"}
    provider_id = body["provider_id"]

    pending_resp = client.get("/api/clinicians/pending")
    assert pending_resp.status_code == 200
    pending_ids = {row["provider_id"] for row in pending_resp.json()}
    if body["license_status"] == "UNVERIFIED":
        assert provider_id in pending_ids
    else:
        assert provider_id not in pending_ids

    if body["license_status"] == "UNVERIFIED":
        verify_resp = client.post(
            f"/api/clinicians/{provider_id}/verify",
            json={"action": "VERIFY", "notes": "Approved in demo", "reviewer": "admin"},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["provider"]["license_status"] == "VERIFIED"

    history_resp = client.get(f"/api/clinicians/{provider_id}/verification-history")
    assert history_resp.status_code == 200
    events = [row["event_type"] for row in history_resp.json()]
    assert "APPLIED" in events
    assert "CONSENT_SMS_DISPATCH" in events
    assert "CONSENT_PRIVACY_POLICY" in events
    if body["license_status"] == "UNVERIFIED":
        assert "VERIFIED" in events
    else:
        assert body["license_status"] == "VERIFIED"
