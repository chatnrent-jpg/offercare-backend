from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.seed import seed_saint_judes_demo
from app.services.shift_cascade import advance_cascade, get_cascade_status
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_cascade_status_after_initial_notify(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    status = get_cascade_status(db, offer_id)
    assert status.offer_status == "BROADCASTING"
    assert len(status.notified) == 1
    assert status.notified[0].full_name == "Nurse A"
    assert status.next_candidate is not None
    assert status.next_candidate.full_name != "Nurse A"
    assert status.next_candidate.rank > status.notified[0].rank


def test_cascade_too_early_without_force(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SNIPER_CASCADE_TIMEOUT_SECONDS", 90)
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    result = advance_cascade(db, offer_id, force=False)
    assert result.status == "too_early"
    assert result.delivery is None
    assert result.cascade.seconds_until_eligible > 0


def test_cascade_advances_to_next_clinician(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    before = get_cascade_status(db, offer_id)
    assert before.next_candidate is not None

    result = advance_cascade(db, offer_id, force=True)
    assert result.status == "advanced"
    assert result.delivery is not None
    assert result.delivery.phone_number == before.next_candidate.phone_number
    assert len(result.cascade.notified) == 2


def test_cascade_stops_after_lock(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock = lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")
    assert lock.status == "locked"

    result = advance_cascade(db, offer_id, force=True)
    assert result.status == "already_locked"
    assert result.delivery is None


def test_cascade_api_flow(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = seeded["offer_id"]

    notify_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )
    assert notify_resp.status_code == 200

    status_resp = client.get(f"/shift-sniper/offers/{offer_id}/cascade")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["notified_count"] == 1
    assert body["next_candidate"]["full_name"] != "Nurse A"

    cascade_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/cascade",
        json={"reply_keyword": "YES", "force": True},
    )
    assert cascade_resp.status_code == 200
    assert cascade_resp.json()["status"] == "advanced"
    assert cascade_resp.json()["delivery"]["phone_number"] == body["next_candidate"]["phone_number"]
