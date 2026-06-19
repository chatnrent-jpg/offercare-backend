from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, OfferCareJobOffer
from app.seed import seed_saint_judes_demo
from app.services.shift_offer_generator import auto_create_shifts_for_facility, list_open_shifts
from app.services.shift_ranking import notify_top_clinicians_for_offer, rank_offer_from_db
from app.services.shift_schedule import apply_default_shift_schedule, resolve_offer_shift_window
from app.services.sms import build_shift_alert_message


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_apply_default_shift_schedule_sets_window() -> None:
    offer = OfferCareJobOffer(
        facility_id=UUID("00000000-0000-0000-0000-000000000001"),
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
    )
    apply_default_shift_schedule(offer)
    assert offer.shift_starts_at is not None
    assert offer.shift_ends_at is not None
    assert offer.shift_ends_at > offer.shift_starts_at


def test_seed_demo_offer_has_schedule(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == UUID(seeded["offer_id"])).one()
    assert offer.shift_starts_at is not None
    assert offer.shift_ends_at is not None


def test_open_shifts_include_shift_times(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    rows = list_open_shifts(db, county="Baltimore", shift_role="ICU_RN")
    match = next((row for row in rows if str(row["offer_id"]) == seeded["offer_id"]), None)
    assert match is not None
    assert match["shift_starts_at"] is not None
    assert match["shift_ends_at"] is not None


def test_rank_response_includes_shift_schedule(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    ranking = rank_offer_from_db(db, UUID(seeded["offer_id"]))
    assert ranking.shift_starts_at is not None
    assert ranking.shift_ends_at is not None


def test_sms_alert_includes_shift_window(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == UUID(seeded["offer_id"])).one()
    start, end = resolve_offer_shift_window(offer)
    message = build_shift_alert_message(
        facility_name="Saint Jude's ICU",
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        shift_starts_at=start,
        shift_ends_at=end,
    )
    assert "ET" in message


def test_notify_message_contains_schedule(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    notified = notify_top_clinicians_for_offer(db, UUID(seeded["offer_id"]), max_recipients=1)
    assert "ET" in notified.deliveries[0].message_body


def test_starts_after_filter(db: Session) -> None:
    facility = MarylandFacility(
        name="Schedule Hospital",
        facility_type="HOSPITAL",
        county="Montgomery County",
        state="MD",
    )
    db.add(facility)
    db.flush()
    past_offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ER_RN",
        hourly_pay_rate=100.0,
        compliance_lock_status="BROADCASTING",
        shift_starts_at=datetime.now(timezone.utc) - timedelta(days=2),
        shift_ends_at=datetime.now(timezone.utc) - timedelta(days=2, hours=-12),
    )
    future_offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
        compliance_lock_status="BROADCASTING",
        shift_starts_at=datetime.now(timezone.utc) + timedelta(days=2),
        shift_ends_at=datetime.now(timezone.utc) + timedelta(days=2, hours=12),
    )
    db.add(past_offer)
    db.add(future_offer)
    db.commit()

    rows = list_open_shifts(db, starts_after=datetime.now(timezone.utc))
    roles = {str(row["shift_role"]) for row in rows if row["facility_id"] == facility.facility_id}
    assert roles == {"ICU_RN"}


def test_auto_create_assigns_schedule(db: Session) -> None:
    facility = MarylandFacility(
        name="Auto Schedule Hospital",
        facility_type="HOSPITAL",
        county="Anne Arundel County",
        state="MD",
    )
    db.add(facility)
    db.commit()
    result = auto_create_shifts_for_facility(db, facility)
    assert result.created_offers
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == result.created_offers[0]).one()
    assert offer.shift_starts_at is not None
    assert offer.shift_ends_at is not None


def test_open_shifts_api_returns_schedule(client: TestClient, db: Session) -> None:
    seed_saint_judes_demo(db)
    response = client.get("/api/shifts/open", params={"state": "MD"})
    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["shift_starts_at"] is not None
    assert rows[0]["shift_ends_at"] is not None
