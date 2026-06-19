from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicalPlacementLedger, MarylandFacility, MarylandProvider, OfferCareJobOffer, ShiftNotificationLog
from app.seed import seed_saint_judes_demo
from app.services.license_verification import is_valid_npi
from app.services.shift_lock import is_lock_keyword, lock_shift_from_sms_reply, normalize_phone
from app.services.shift_ranking import notify_top_clinicians_for_offer
from app.services.shift_schedule import apply_default_shift_schedule
from tests.pollution_cleanup import purge_lock_test_pollution


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_normalize_phone_and_keyword() -> None:
    assert normalize_phone("4105550001") == "+14105550001"
    assert normalize_phone("+14105550001") == "+14105550001"
    assert is_lock_keyword("yes")
    assert not is_lock_keyword("maybe")


def test_lock_shift_after_notify(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = uuid.UUID(seeded["offer_id"])

    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    result = lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")
    assert result.status == "locked"
    assert result.offer_id == offer_id
    assert result.placement_id is not None

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    assert offer is not None
    assert offer.compliance_lock_status == "LOCKED"
    assert offer.assigned_provider_id == result.provider_id

    placement = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.placement_id == result.placement_id)
        .first()
    )
    assert placement is not None
    assert placement.facility_name == "Saint Jude's ICU"
    assert placement.clinical_unit == "ICU_RN"


def _make_valid_npi(seed: int) -> str:
    base9 = f"{seed % 1_000_000_000:09d}"
    for check in range(10):
        candidate = f"{base9}{check}"
        if is_valid_npi(candidate):
            return candidate
    raise ValueError("unable to build valid NPI")


def test_second_lock_attempt_rejected(db: Session) -> None:
    purge_lock_test_pollution(db)
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    facility = MarylandFacility(
        name=f"Lock Test Hospital {token}",
        facility_type="HOSPITAL",
        county="District of Columbia",
        state="DC",
    )
    db.add(facility)
    db.flush()

    providers: list[MarylandProvider] = []
    for idx, suffix in enumerate(("A", "B")):
        provider = MarylandProvider(
            full_name=f"Lock Nurse {suffix} {token}",
            email=f"lock.{suffix}.{token}@offercare.demo",
            phone_number=f"+1202{(seed + idx) % 10_000_000:07d}",
            npi_number=_make_valid_npi(seed + idx),
            md_license_number=f"RN-DC-{token}-{suffix}",
            state="DC",
            license_status="VERIFIED",
            min_hourly_rate=80.0,
            response_propensity=0.9,
            fatigue_score=0.0,
        )
        db.add(provider)
        db.flush()
        providers.append(provider)

    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        compliance_lock_status="BROADCASTING",
    )
    apply_default_shift_schedule(offer)
    db.add(offer)
    db.flush()

    for provider in providers:
        db.add(
            ShiftNotificationLog(
                offer_id=offer.offer_id,
                provider_id=provider.provider_id,
                channel="SMS",
                status="SENT",
                message_body="Reply YES to lock this shift.",
            )
        )
    db.commit()

    try:
        first = lock_shift_from_sms_reply(db, from_phone=providers[0].phone_number, message_body="YES")
        assert first.status == "locked"

        second = lock_shift_from_sms_reply(db, from_phone=providers[1].phone_number, message_body="YES")
        assert second.status == "already_locked"
    finally:
        purge_lock_test_pollution(db)


def test_api_seed_notify_and_simulate_reply(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/saint-judes")
    assert seed_resp.status_code == 200
    offer_id = seed_resp.json()["offer_id"]

    notify_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )
    assert notify_resp.status_code == 200

    lock_resp = client.post(
        "/shift-sniper/simulate-reply",
        json={"phone_number": "+14105550001", "body": "YES"},
    )
    assert lock_resp.status_code == 200
    body = lock_resp.json()
    assert body["status"] == "locked"
    assert body["offer_id"] == offer_id
    assert body["placement_id"] is not None


def test_twilio_webhook_returns_twiml(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/saint-judes")
    offer_id = seed_resp.json()["offer_id"]
    client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )

    twilio_resp = client.post(
        "/shift-sniper/twilio/sms",
        data={"From": "+14105550001", "Body": "YES"},
    )
    assert twilio_resp.status_code == 200
    assert twilio_resp.headers["content-type"].startswith("application/xml")
    assert "<Message>" in twilio_resp.text
    assert "Shift locked" in twilio_resp.text
