from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, MarylandProvider, OfferCareJobOffer
from app.seed import seed_nursing_home_demo
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.clinician_auth import create_portal_account
from app.services.license_verification import verify_clinician
from app.services.shift_lock import lock_shift_for_provider


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _reset_demo_offer(db: Session, offer_id: UUID) -> None:
    db.query(ClinicalPlacementLedger).filter(
        ClinicalPlacementLedger.offer_id == offer_id
    ).delete(synchronize_session=False)
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    assert offer is not None
    offer.compliance_lock_status = "BROADCASTING"
    offer.assigned_provider_id = None
    db.commit()


def _verified_portal_lpn(db: Session, client: TestClient) -> tuple[MarylandProvider, dict[str, str]]:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name="Portal LPN Locker",
        email=f"portal.lpn.locker.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"portal.lpn.locker.{token}@offercare.demo"),
        md_license_number=f"LPN-MD-{token.upper()}",
        state="MD",
        credential_type="LPN",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=30.0,
        response_propensity=0.9,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.flush()
    create_portal_account(db, provider.provider_id, "SecretPass1")
    verify_clinician(db, provider.provider_id, action="VERIFY", reviewer="admin")
    login = client.post(
        "/api/clinicians/login",
        json={"email": provider.email, "password": "SecretPass1"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return provider, headers


def test_lock_shift_for_provider_creates_placement(db: Session) -> None:
    seeded = seed_nursing_home_demo(db)
    _reset_demo_offer(db, UUID(seeded["offer_id"]))
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "snf.lpn.a@offercare.demo")
        .first()
    )
    assert provider is not None

    result = lock_shift_for_provider(db, provider=provider, offer_id=UUID(seeded["offer_id"]))
    assert result.status == "locked"
    assert result.placement_id is not None

    placement = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.placement_id == result.placement_id)
        .first()
    )
    assert placement is not None
    assert placement.assigned_clinician_id == provider.provider_id


def test_lock_shift_for_provider_rejects_unverified(db: Session) -> None:
    seeded = seed_nursing_home_demo(db)
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name="Unverified LPN",
        email=f"unverified.lpn.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"unverified.lpn.{token}@offercare.demo"),
        md_license_number=f"LPN-MD-{token.upper()}",
        state="MD",
        credential_type="LPN",
        service_lines="NURSING_HOME",
        license_status="UNVERIFIED",
        min_hourly_rate=30.0,
        response_propensity=0.9,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.commit()

    result = lock_shift_for_provider(db, provider=provider, offer_id=UUID(seeded["offer_id"]))
    assert result.status == "rejected"


def test_lock_shift_for_provider_rejects_non_matching_credential(db: Session) -> None:
    seeded = seed_nursing_home_demo(db)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "snf.cna.a@offercare.demo")
        .first()
    )
    assert provider is not None

    result = lock_shift_for_provider(db, provider=provider, offer_id=UUID(seeded["offer_id"]))
    assert result.status == "not_matched"


def test_lock_matched_shift_endpoint(db: Session, client: TestClient) -> None:
    seeded = seed_nursing_home_demo(db)
    _reset_demo_offer(db, UUID(seeded["offer_id"]))
    provider, headers = _verified_portal_lpn(db, client)

    response = client.post(
        f"/api/clinicians/me/matched-shifts/{seeded['offer_id']}/lock",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "locked"
    assert body["provider_id"] == str(provider.provider_id)

    second = client.post(
        f"/api/clinicians/me/matched-shifts/{seeded['offer_id']}/lock",
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "already_locked"


def test_lock_matched_shift_endpoint_requires_auth(client: TestClient) -> None:
    response = client.post(f"/api/clinicians/me/matched-shifts/{uuid.uuid4()}/lock")
    assert response.status_code == 401


def test_portal_includes_lock_matched_shift_ui(client: TestClient) -> None:
    html = client.get("/portal/")
    assert html.status_code == 200
    js = client.get("/portal/app.js")
    assert js.status_code == 200
    assert "lockMatchedShift" in js.text
    assert "/api/clinicians/me/matched-shifts/" in js.text
    assert "lock-shift-btn" in js.text
