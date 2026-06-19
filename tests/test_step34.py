from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.seed import seed_hackensack_demo, seed_inova_fairfax_demo, seed_saint_judes_demo
from app.services.shift_offer_generator import list_open_shifts
from app.services.shift_ranking import rank_offer_from_db


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_hackensack_seed_creates_nj_facility_and_offer(db: Session) -> None:
    seeded = seed_hackensack_demo(db)
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == UUID(seeded["facility_id"]))
        .one()
    )
    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == UUID(seeded["offer_id"]))
        .one()
    )
    assert facility.name == "Hackensack Meridian ICU"
    assert facility.state == "NJ"
    assert facility.county == "Bergen County"
    assert offer.shift_role == "ICU_RN"
    assert offer.hourly_pay_rate == 122.0
    assert offer.compliance_lock_status == "BROADCASTING"
    assert offer.shift_starts_at is not None
    assert offer.shift_ends_at is not None


def test_hackensack_seed_creates_nj_clinicians(db: Session) -> None:
    seeded = seed_hackensack_demo(db)
    provider_ids = [UUID(pid) for pid in seeded["provider_ids"].split(",")]
    rows = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.provider_id.in_(provider_ids))
        .all()
    )
    assert len(rows) == 2
    assert {row.state for row in rows} == {"NJ"}
    assert {row.license_status for row in rows} == {"VERIFIED"}


def test_hackensack_seed_is_idempotent(db: Session) -> None:
    first = seed_hackensack_demo(db)
    second = seed_hackensack_demo(db)
    assert first["facility_id"] == second["facility_id"]
    assert first["offer_id"] == second["offer_id"]
    assert first["provider_ids"] == second["provider_ids"]


def test_sniper_ranks_only_nj_clinicians_for_hackensack_offer(db: Session) -> None:
    seed_saint_judes_demo(db)
    seed_inova_fairfax_demo(db)
    seeded = seed_hackensack_demo(db)
    ranking = rank_offer_from_db(db, UUID(seeded["offer_id"]))
    assert ranking.facility_state == "NJ"
    assert ranking.ranked
    provider_ids = [row.provider_id for row in ranking.ranked]
    states = {
        row.state
        for row in db.query(MarylandProvider)
        .filter(MarylandProvider.provider_id.in_(provider_ids))
        .all()
    }
    assert states == {"NJ"}


def test_open_shifts_filter_by_new_jersey(db: Session) -> None:
    seed_hackensack_demo(db)
    rows = list_open_shifts(db, state="NJ")
    assert rows
    assert all(row["state"] == "NJ" for row in rows)
    assert any(row["facility_name"] == "Hackensack Meridian ICU" for row in rows)


def test_hackensack_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/hackensack")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "NJ"
    assert body["offer_id"]
    assert body["facility_id"]
    assert body["provider_ids"]


def test_open_shifts_api_nj_param(client: TestClient, db: Session) -> None:
    seed_hackensack_demo(db)
    response = client.get("/api/shifts/open", params={"state": "NJ"})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["state"] == "NJ"


def test_admin_dashboard_includes_hackensack_seed_button(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-hackensack-btn" in html.text
    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "/api/seed/hackensack" in js.text
