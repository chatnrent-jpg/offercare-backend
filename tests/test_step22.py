from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, OfferCareJobOffer
from app.seed import seed_saint_judes_demo
from app.services.shift_offer_generator import get_open_shift_filters, list_open_shifts


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_shift_filters_endpoint(client: TestClient, db: Session) -> None:
    seed_saint_judes_demo(db)
    response = client.get("/api/shifts/filters")
    assert response.status_code == 200
    body = response.json()
    assert "Baltimore County" in body["counties"]
    assert "ICU_RN" in body["shift_roles"]


def test_open_shifts_filter_by_role(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    facility = MarylandFacility(
        name=f"Role Filter Hospital {token}",
        facility_type="HOSPITAL",
        county="Montgomery County",
        state="MD",
    )
    db.add(facility)
    db.flush()
    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="ICU_RN",
        hourly_pay_rate=125.0,
        compliance_lock_status="BROADCASTING",
    )
    db.add(offer)
    db.commit()

    rows = [
        row
        for row in list_open_shifts(db, shift_role="ICU_RN")
        if row["facility_id"] == facility.facility_id
    ]
    assert len(rows) == 1
    assert rows[0]["shift_role"] == "ICU_RN"
    assert str(rows[0]["offer_id"]) == str(offer.offer_id)


def test_open_shifts_filter_by_min_pay(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    facility = MarylandFacility(
        name=f"Filter Hospital {token}",
        facility_type="HOSPITAL",
        county="Howard County",
    )
    db.add(facility)
    db.flush()
    db.add(
        OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="ER_RN",
            hourly_pay_rate=115.0,
            compliance_lock_status="BROADCASTING",
        )
    )
    db.add(
        OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role="MED_SURG_RN",
            hourly_pay_rate=90.0,
            compliance_lock_status="BROADCASTING",
        )
    )
    db.commit()

    rows = [
        row
        for row in list_open_shifts(db, county="Howard", min_pay=100.0)
        if row["facility_id"] == facility.facility_id
    ]
    assert len(rows) == 1
    assert rows[0]["shift_role"] == "ER_RN"


def test_open_shifts_api_query_params(client: TestClient, db: Session) -> None:
    seed_saint_judes_demo(db)
    response = client.get("/api/shifts/open", params={"county": "Baltimore", "shift_role": "ICU_RN", "min_pay": 100})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["shift_role"] == "ICU_RN"
    assert rows[0]["hourly_pay_rate"] >= 100


def test_get_open_shift_filters_service(db: Session) -> None:
    seed_saint_judes_demo(db)
    options = get_open_shift_filters(db)
    assert options["counties"]
    assert options["shift_roles"]
