from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ShiftNotificationLog
from app.seed import seed_nj_nursing_home_demo
from app.services.push_alerts import build_matched_shift_alert_push, build_shift_alert_push
from app.services.push_subscriptions import register_push_subscription
from app.services.matched_shift_alerts import (
    list_matched_providers_for_offer,
    notify_matched_clinicians_for_offer,
)
from app.services.shift_offer_generator import auto_create_shifts_for_facilities


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_matched_shift_alert_push_mentions_portal() -> None:
    title, body = build_matched_shift_alert_push(
        facility_name="Paramus SNF at Bergen",
        shift_role="GNA",
        hourly_pay_rate=24.0,
    )
    assert "Matched shift" in title
    assert "/portal" in body


def test_build_shift_alert_push_mentions_portal_and_sms() -> None:
    _title, body = build_shift_alert_push(
        facility_name="Saint Jude's ICU",
        shift_role="ICU_RN",
        hourly_pay_rate=120.0,
    )
    assert "/portal" in body
    assert "YES" in body


def test_list_matched_providers_for_offer_requires_push_subscription(db: Session) -> None:
    seeded = seed_nj_nursing_home_demo(db)
    offer_id = UUID(seeded["offer_id"])
    assert not list_matched_providers_for_offer(db, offer_id)

    cna_id = UUID(seeded["provider_ids"].split(",")[1])
    register_push_subscription(
        db,
        cna_id,
        endpoint="https://push.example.test/nj-list",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    matched = list_matched_providers_for_offer(db, offer_id)
    assert len(matched) == 1
    assert matched[0].email == "nj.snf.cna.a@offercare.demo"


def test_notify_matched_clinicians_sends_push(db: Session) -> None:
    seeded = seed_nj_nursing_home_demo(db)
    offer_id = UUID(seeded["offer_id"])
    provider_id = UUID(seeded["provider_ids"].split(",")[1])
    register_push_subscription(
        db,
        provider_id,
        endpoint="https://push.example.test/nj-cna",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    sent = notify_matched_clinicians_for_offer(db, offer_id)
    assert sent >= 1
    logs = (
        db.query(ShiftNotificationLog)
        .filter(
            ShiftNotificationLog.offer_id == offer_id,
            ShiftNotificationLog.channel == "MATCHED_PUSH",
            ShiftNotificationLog.provider_id == provider_id,
        )
        .all()
    )
    assert logs


def test_auto_create_shifts_skips_matched_push_when_disabled(db: Session) -> None:
    seeded = seed_nj_nursing_home_demo(db)
    facility_id = UUID(seeded["facility_id"])
    cna_id = UUID(seeded["provider_ids"].split(",")[1])
    register_push_subscription(
        db,
        cna_id,
        endpoint="https://push.example.test/nj-auto",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    _facilities, _offers_created, matched_push = auto_create_shifts_for_facilities(
        db,
        [facility_id],
        notify_matched_push=False,
    )
    assert matched_push == 0


def test_notify_matched_endpoint(client: TestClient, db: Session) -> None:
    seeded = seed_nj_nursing_home_demo(db)
    offer_id = seeded["offer_id"]
    provider_id = UUID(seeded["provider_ids"].split(",")[1])
    register_push_subscription(
        db,
        provider_id,
        endpoint="https://push.example.test/nj-endpoint",
        p256dh_key="test-p256dh",
        auth_key="test-auth",
    )
    response = client.post(f"/api/shifts/offers/{offer_id}/notify-matched")
    assert response.status_code == 200
    body = response.json()
    assert body["matched_push_alerts_sent"] >= 1
