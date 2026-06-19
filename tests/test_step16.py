from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_saint_judes_demo
from app.services.shift_ranking import notify_top_clinicians_for_offer


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_admin_dashboard_includes_sniper_and_integrations(client: TestClient) -> None:
    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Shift Sniper intelligence" in response.text
    assert "Integrations" in response.text
    assert "relearn-scores-btn" in response.text


def test_list_sniper_scores_endpoint(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    response = client.get("/shift-sniper/scores")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 3
    nurse_a = next(row for row in rows if row["full_name"] == "Nurse A")
    assert nurse_a["notifications_total"] >= 1
    assert "response_propensity" in nurse_a
    assert "fatigue_score" in nurse_a
    assert nurse_a["license_status"] == "VERIFIED"


def test_list_sniper_scores_requires_admin_key(client: TestClient) -> None:
    unauth = TestClient(client.app)
    response = unauth.get("/shift-sniper/scores")
    assert response.status_code == 401
