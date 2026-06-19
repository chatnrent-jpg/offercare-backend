from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.seed import seed_nj_nursing_home_demo
from app.services.shift_matching import list_matched_shifts_for_provider
from app.services.shift_ranking import rank_offer_from_db


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_nj_nursing_home_seed_creates_post_acute_demo(db: Session) -> None:
    payload = seed_nj_nursing_home_demo(db)
    assert payload["state"] == "NJ"
    assert payload["facility_type"] == "NURSING_HOME"
    assert payload["offer_id"]
    assert payload["provider_ids"]


def test_nj_nursing_home_seed_ranks_cna_for_gna_shift(db: Session) -> None:
    payload = seed_nj_nursing_home_demo(db)
    ranking = rank_offer_from_db(db, UUID(payload["offer_id"]))
    assert ranking.ranked
    assert all(row.credential_type == "CNA" for row in ranking.ranked if row.credential_type != "LPN")
    assert any(row.credential_type == "CNA" for row in ranking.ranked)


def test_nj_cna_sees_matched_gna_shift(db: Session) -> None:
    payload = seed_nj_nursing_home_demo(db)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo")
        .first()
    )
    assert provider is not None
    matched = list_matched_shifts_for_provider(db, provider, limit=20)
    assert payload["offer_id"] in {str(row["offer_id"]) for row in matched}


def test_nj_nursing_home_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/seed/nj-nursing-home")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "NJ"
    assert body["facility_type"] == "NURSING_HOME"


def test_admin_dashboard_includes_nj_nursing_home_seed(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "seed-nj-nursing-home-btn" in html.text
    js = client.get("/admin/app.js")
    assert "/api/seed/nj-nursing-home" in js.text
