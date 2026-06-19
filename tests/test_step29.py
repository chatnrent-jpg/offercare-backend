from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import OfferCareJobOffer
from app.seed import seed_saint_judes_demo
from app.services.ops_metrics import list_ops_audit_events
from app.services.shift_schedule import resolve_offer_shift_window
from app.services.shift_schedule_editor import update_offer_shift_schedule


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_update_offer_shift_schedule_persists(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    new_start = datetime.now(timezone.utc) + timedelta(days=3)
    new_end = new_start + timedelta(hours=12)

    row = update_offer_shift_schedule(
        db,
        offer_id,
        shift_starts_at=new_start,
        shift_ends_at=new_end,
    )

    assert row["shift_starts_at"].replace(tzinfo=timezone.utc) == new_start
    assert row["shift_ends_at"].replace(tzinfo=timezone.utc) == new_end
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).one()
    start, end = resolve_offer_shift_window(offer)
    assert start == new_start
    assert end == new_end


def test_update_offer_shift_schedule_rejects_invalid_window(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    start = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(ValueError, match="invalid_schedule_window"):
        update_offer_shift_schedule(
            db,
            offer_id,
            shift_starts_at=start,
            shift_ends_at=start,
        )


def test_update_offer_shift_schedule_rejects_locked(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).one()
    offer.compliance_lock_status = "LOCKED"
    db.commit()
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=12)
    with pytest.raises(ValueError, match="offer_locked"):
        update_offer_shift_schedule(
            db,
            offer_id,
            shift_starts_at=start,
            shift_ends_at=end,
        )


def test_update_offer_shift_schedule_logs_audit(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    start = datetime.now(timezone.utc) + timedelta(days=4)
    end = start + timedelta(hours=12)
    update_offer_shift_schedule(
        db,
        offer_id,
        shift_starts_at=start,
        shift_ends_at=end,
        actor="admin_test",
    )
    events = list_ops_audit_events(db, limit=20)
    match = next((row for row in events if row.entity_id == offer_id and row.event_type == "SHIFT_SCHEDULE"), None)
    assert match is not None
    assert match.actor == "admin_test"


def test_get_shift_offer_api(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    response = client.get(f"/api/shifts/offers/{seeded['offer_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["offer_id"] == seeded["offer_id"]
    assert body["shift_starts_at"] is not None
    assert body["shift_ends_at"] is not None


def test_get_shift_offer_api_not_found(client: TestClient) -> None:
    response = client.get(f"/api/shifts/offers/{uuid4()}")
    assert response.status_code == 404


def test_patch_shift_schedule_api(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    new_start = datetime.now(timezone.utc) + timedelta(days=5)
    new_end = new_start + timedelta(hours=12)
    response = client.patch(
        f"/api/shifts/offers/{seeded['offer_id']}/schedule",
        json={
            "shift_starts_at": new_start.isoformat(),
            "shift_ends_at": new_end.isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["shift_starts_at"].replace("Z", "+00:00")) == new_start
    assert datetime.fromisoformat(body["shift_ends_at"].replace("Z", "+00:00")) == new_end


def test_patch_shift_schedule_api_invalid_window(client: TestClient, db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    response = client.patch(
        f"/api/shifts/offers/{seeded['offer_id']}/schedule",
        json={
            "shift_starts_at": start.isoformat(),
            "shift_ends_at": start.isoformat(),
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_schedule_window"


def test_admin_dashboard_includes_schedule_editor(client: TestClient) -> None:
    html = client.get("/admin")
    assert html.status_code == 200
    assert "schedule-dialog" in html.text
    assert "schedule-form" in html.text

    js = client.get("/admin/app.js")
    assert js.status_code == 200
    assert "Edit schedule" in js.text
    assert "openScheduleEditor" in js.text
