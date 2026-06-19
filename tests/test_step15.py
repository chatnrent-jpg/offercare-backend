from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ClinicianPushSubscription, MarylandProvider, ShiftNotificationLog
from app.seed import seed_saint_judes_demo
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer
from app.services.sniper_learning import (
    build_sniper_score_snapshot,
    compute_fatigue_score,
    compute_response_propensity,
    refresh_all_provider_sniper_scores,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_compute_response_propensity_prior_when_no_history() -> None:
    assert compute_response_propensity(notifications=0, acceptances=0) == 0.5


def test_compute_response_propensity_increases_with_acceptances() -> None:
    low = compute_response_propensity(notifications=10, acceptances=1)
    high = compute_response_propensity(notifications=10, acceptances=8)
    assert high > low


def test_compute_fatigue_score_caps() -> None:
    assert compute_fatigue_score(recent_notifications=0) == 0.0
    assert compute_fatigue_score(recent_notifications=4, per_sms=0.25) == 1.0
    assert compute_fatigue_score(recent_notifications=100, per_sms=0.25, max_fatigue=5.0) == 5.0


def test_notify_and_lock_refresh_scores(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])

    nurse_a = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.full_name == "Nurse A")
        .one()
    )
    nurse_a.response_propensity = 0.9
    nurse_a.fatigue_score = 0.0
    db.query(ClinicianPushSubscription).filter(
        ClinicianPushSubscription.provider_id == nurse_a.provider_id
    ).delete(synchronize_session=False)
    db.commit()
    before = build_sniper_score_snapshot(db, nurse_a.provider_id)

    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    db.refresh(nurse_a)
    after_notify = build_sniper_score_snapshot(db, nurse_a.provider_id)
    assert after_notify.notifications_total == before.notifications_total + 2
    assert float(nurse_a.fatigue_score) == after_notify.fatigue_score
    assert float(nurse_a.response_propensity) == after_notify.response_propensity
    assert after_notify.response_propensity <= before.response_propensity

    lock_shift_from_sms_reply(
        db,
        from_phone=nurse_a.phone_number,
        message_body="YES",
    )
    db.refresh(nurse_a)
    after_lock = build_sniper_score_snapshot(db, nurse_a.provider_id)
    assert after_lock.acceptances_total == before.acceptances_total + 1
    assert float(nurse_a.response_propensity) == after_lock.response_propensity
    assert after_lock.response_propensity >= after_notify.response_propensity


def test_relearn_endpoint(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/saint-judes")
    assert seed_resp.status_code == 200
    offer_id = seed_resp.json()["offer_id"]

    notify_resp = client.post(
        f"/shift-sniper/offers/{offer_id}/notify",
        json={"max_recipients": 1, "reply_keyword": "YES"},
    )
    assert notify_resp.status_code == 200
    provider_id = notify_resp.json()["deliveries"][0]["provider_id"]

    relearn_resp = client.post("/shift-sniper/relearn-scores")
    assert relearn_resp.status_code == 200
    body = relearn_resp.json()
    assert body["updated"] >= 3
    notified = next(row for row in body["providers"] if row["provider_id"] == provider_id)
    assert notified["notifications_total"] >= 1
    assert notified["fatigue_score"] >= 0.25


def test_refresh_all_provider_sniper_scores(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    snapshots = refresh_all_provider_sniper_scores(db)
    assert len(snapshots) >= 3
    nurse_a = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.full_name == "Nurse A")
        .one()
    )
    notified = next(row for row in snapshots if row.provider_id == nurse_a.provider_id)
    assert notified.notifications_total >= 1
    assert build_sniper_score_snapshot(db, notified.provider_id).response_propensity == notified.response_propensity
