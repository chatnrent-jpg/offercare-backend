from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_inova_fairfax_demo, seed_saint_judes_demo
from app.services.shift_offer_generator import get_open_shift_filters, list_open_shifts
from app.services.shift_ranking import rank_offer_from_db
from app.services.states import grid_region_label, normalize_state, supported_states


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_supported_states_include_mid_atlantic() -> None:
    states = supported_states()
    assert "MD" in states
    assert "VA" in states
    assert "DC" in states
    assert "PA" in states
    assert "DE" in states
    assert "NJ" in states


def test_normalize_state_aliases() -> None:
    assert normalize_state("virginia") == "VA"
    assert normalize_state("Maryland") == "MD"
    assert normalize_state("DC") == "DC"
    assert normalize_state("pennsylvania") == "PA"
    assert normalize_state("delaware") == "DE"
    assert normalize_state("new jersey") == "NJ"


def test_grid_region_label() -> None:
    assert "Mid-Atlantic" in grid_region_label()


def test_shift_filters_include_states(client: TestClient, db: Session) -> None:
    seed_saint_judes_demo(db)
    seed_inova_fairfax_demo(db)
    response = client.get("/api/shifts/filters")
    assert response.status_code == 200
    body = response.json()
    assert "MD" in body["states"]
    assert "VA" in body["states"]


def test_open_shifts_filter_by_state(db: Session) -> None:
    seed_saint_judes_demo(db)
    seed_inova_fairfax_demo(db)
    va_rows = list_open_shifts(db, state="VA")
    md_rows = list_open_shifts(db, state="MD")
    assert va_rows
    assert md_rows
    assert all(row["state"] == "VA" for row in va_rows)
    assert all(row["state"] == "MD" for row in md_rows)


def test_sniper_ranks_only_matching_state_clinicians(db: Session) -> None:
    from app.models import MarylandProvider

    seeded = seed_saint_judes_demo(db)
    va_seeded = seed_inova_fairfax_demo(db)
    md_offer = UUID(seeded["offer_id"])
    va_offer = UUID(va_seeded["offer_id"])

    md_rank = rank_offer_from_db(db, md_offer)
    va_rank = rank_offer_from_db(db, va_offer)
    assert md_rank.facility_state == "MD"
    assert va_rank.facility_state == "VA"
    assert md_rank.ranked
    assert va_rank.ranked

    md_ids = [row.provider_id for row in md_rank.ranked]
    va_ids = [row.provider_id for row in va_rank.ranked]
    md_states = {
        row.state
        for row in db.query(MarylandProvider).filter(MarylandProvider.provider_id.in_(md_ids)).all()
    }
    va_states = {
        row.state
        for row in db.query(MarylandProvider).filter(MarylandProvider.provider_id.in_(va_ids)).all()
    }
    assert md_states == {"MD"}
    assert va_states == {"VA"}


def test_grid_states_endpoint(client: TestClient) -> None:
    response = client.get("/api/grid/states")
    assert response.status_code == 200
    body = response.json()
    assert "MD" in body["states"]
    assert "region" in body


def test_inova_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/inova-fairfax")
    assert response.status_code == 200
    assert response.json()["state"] == "VA"


def test_open_shifts_api_state_param(client: TestClient, db: Session) -> None:
    seed_inova_fairfax_demo(db)
    response = client.get("/api/shifts/open", params={"state": "VA"})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["state"] == "VA"


def test_env_example_documents_multistate() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "SUPPORTED_STATES" in text
