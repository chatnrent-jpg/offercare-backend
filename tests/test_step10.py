from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, MarylandFacility
from app.schemas import ClinicianApplyRequest
from app.seed import seed_saint_judes_demo
from app.services.license_verification import apply_as_clinician, is_valid_npi, verify_clinician
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_offer_generator import auto_create_shifts_for_facility, list_open_shifts
from app.services.shift_ranking import notify_top_clinicians_for_offer
from app.services.vms_submission import submit_placement_to_vms


def _make_valid_npi(seed: int) -> str:
    base9 = f"{seed % 1_000_000_000:09d}"
    for check in range(10):
        candidate = f"{base9}{check}"
        if is_valid_npi(candidate):
            return candidate
    raise ValueError("unable to build valid NPI")


def _apply_with_password(db: Session, password: str = "SecretPass1") -> tuple:
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    payload = ClinicianApplyRequest(
        full_name="Portal Nurse",
        email=f"portal.{token}@offercare.demo",
        phone_number=f"410{seed % 10_000_000:07d}",
        npi_number=_make_valid_npi(seed),
        md_license_number=f"RN-MD-{token.upper()}",
        min_hourly_rate=95.0,
        password=password,
    )
    provider, _ = apply_as_clinician(db, payload)
    return provider, payload.email, password


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_password_hash_roundtrip() -> None:
    from app.auth import hash_password

    stored = hash_password("SecretPass1")
    assert verify_password("SecretPass1", stored)
    assert not verify_password("wrong", stored)


def test_clinician_login_and_me(db: Session, client: TestClient) -> None:
    provider, email, password = _apply_with_password(db)
    login_resp = client.post("/api/clinicians/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/clinicians/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["provider_id"] == str(provider.provider_id)

    app_resp = client.get("/api/clinicians/me/application", headers={"Authorization": f"Bearer {token}"})
    assert app_resp.status_code == 200
    assert app_resp.json()["portal_enabled"] is True
    assert app_resp.json()["provider"]["license_status"] == "UNVERIFIED"


def test_auto_create_shifts_for_facility(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    facility = MarylandFacility(
        name=f"Test Hospital {token}",
        facility_type="HOSPITAL",
        county=f"Test County {token}",
    )
    db.add(facility)
    db.commit()

    result = auto_create_shifts_for_facility(db, facility)
    assert result.created_offers
    assert "ICU_RN" not in result.skipped_roles or len(result.created_offers) >= 1

    open_rows = list_open_shifts(db, county=facility.county)
    assert any(row["facility_id"] == facility.facility_id for row in open_rows)


def test_auto_create_endpoint(client: TestClient) -> None:
    resp = client.post("/api/shifts/auto-create", json={"limit": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["facilities_processed"] >= 0


def test_vms_submission_after_lock(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = uuid.UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock = lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")
    assert lock.status == "locked"
    assert lock.placement_id is not None

    result = submit_placement_to_vms(db, lock.placement_id)
    assert result.status == "SUBMITTED"
    assert result.mode == "dry_run"
    assert result.external_ref

    placement = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.placement_id == lock.placement_id)
        .first()
    )
    assert placement is not None
    assert placement.vms_submission_status == "SUBMITTED"


def test_vms_batch_and_api(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = uuid.UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock = lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")

    submit_resp = client.post(f"/api/vms/placements/{lock.placement_id}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "SUBMITTED"

    batch_resp = client.post("/api/vms/placements/submit-pending?limit=5")
    assert batch_resp.status_code == 200


def test_verified_clinician_portal_status(db: Session, client: TestClient) -> None:
    provider, email, password = _apply_with_password(db)
    verify_clinician(db, provider.provider_id, action="VERIFY", notes="test")

    login_resp = client.post("/api/clinicians/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    app_resp = client.get("/api/clinicians/me/application", headers={"Authorization": f"Bearer {token}"})
    assert app_resp.status_code == 200
    assert app_resp.json()["provider"]["license_status"] == "VERIFIED"
    events = [row["event_type"] for row in app_resp.json()["verification_history"]]
    assert "APPLIED" in events
    assert "VERIFIED" in events
