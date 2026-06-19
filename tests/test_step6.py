from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_saint_judes_demo
from app.services.shift_ranking import notify_top_clinicians_for_offer, rank_offer_from_db
from app.services.sms import send_shift_sms


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_sms_dry_run_by_default() -> None:
    result = send_shift_sms(to_number="+14105550001", message_body="test")
    assert result.mode == "dry_run"
    assert result.status == "DRY_RUN"


def test_seed_rank_and_notify_flow(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = seeded["offer_id"]

    ranking = rank_offer_from_db(db, __import__("uuid").UUID(offer_id))
    assert ranking.notify_order
    assert ranking.ranked[0].full_name == "Nurse A"
    assert ranking.ranked[0].priority_score == 471.25
    assert any(row.full_name == "Nurse C" for row in ranking.eliminated)

    notified = notify_top_clinicians_for_offer(db, __import__("uuid").UUID(offer_id))
    assert notified.deliveries
    assert notified.deliveries[0].mode == "dry_run"
    assert notified.deliveries[0].phone_number == "+14105550001"


def test_api_seed_and_rank_endpoints(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/saint-judes")
    assert seed_resp.status_code == 200
    offer_id = seed_resp.json()["offer_id"]

    rank_resp = client.get(f"/shift-sniper/offers/{offer_id}/rank")
    assert rank_resp.status_code == 200
    body = rank_resp.json()
    assert body["ranked"][0]["full_name"] == "Nurse A"

    notify_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )
    assert notify_resp.status_code == 200
    assert notify_resp.json()["deliveries"][0]["status"] == "DRY_RUN"
