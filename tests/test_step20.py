from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.seed import seed_saint_judes_demo
from app.services.cascade_worker import cascade_worker_status, run_cascade_worker_tick
from app.services.shift_cascade import get_cascade_status
from app.services.shift_ranking import notify_top_clinicians_for_offer


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_cascade_worker_status_endpoint(client: TestClient) -> None:
    response = client.get("/api/ops/cascade-worker/status")
    assert response.status_code == 200
    body = response.json()
    assert "interval_seconds" in body
    assert body["enabled"] is False  # disabled in test conftest


def test_worker_tick_advances_when_eligible(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SNIPER_CASCADE_TIMEOUT_SECONDS", 0)

    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    status = get_cascade_status(db, offer_id)
    assert status.can_advance is True

    results = run_cascade_worker_tick(db)
    assert len(results) == 1
    assert results[0].status == "advanced"
    assert len(get_cascade_status(db, offer_id).notified) == 2


def test_worker_tick_skips_when_disabled(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "SNIPER_CASCADE_TIMEOUT_SECONDS", 0)

    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    assert run_cascade_worker_tick(db) == []


def test_worker_manual_tick_endpoint(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SNIPER_CASCADE_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SNIPER_CASCADE_TIMEOUT_SECONDS", 0)

    seeded = seed_saint_judes_demo(db)
    offer_id = seeded["offer_id"]
    notify_top_clinicians_for_offer(db, UUID(offer_id), max_recipients=1)

    response = client.post("/api/ops/cascade-worker/tick")
    assert response.status_code == 200
    body = response.json()
    assert body["advanced"] == 1
    assert body["results"][0]["status"] == "advanced"


def test_cascade_worker_status_helper() -> None:
    status = cascade_worker_status()
    assert status.interval_seconds >= 1
