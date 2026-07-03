"""Portal step 19 — placements after lock, schedule commitments, demo shift replenish."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import PORTAL_BUILD_ID
from app.models import MarylandProvider
from app.services.demo_portal_accounts import DEMO_PORTAL_PASSWORD, SAMPLE_DEMO_PORTAL_EMAIL
from app.services.demo_portal_lockable import (
    ensure_demo_portal_lockable_shift,
    repair_demo_portal_placements,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_portal_step19_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    css = client.get("/portal/styles.css").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "lastLockedPlacementId" in js
    assert "focusLatestPlacement" in js
    assert "scheduleEventBadge" in js
    assert "placement-highlight" in css
    assert "shift-commitment-row" in css


def test_demo_bootstrap_endpoint_returns_lockable_count(client: TestClient) -> None:
    login = client.post(
        "/api/clinicians/login",
        json={"email": SAMPLE_DEMO_PORTAL_EMAIL, "password": DEMO_PORTAL_PASSWORD},
    )
    if login.status_code == 401:
        pytest.skip("demo login unavailable in this database")
    token = login.json()["access_token"]
    response = client.post(
        "/api/clinicians/me/demo-shift-bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "lockable_count" in body
    assert body["lockable_count"] >= 0


def test_repair_demo_placements_from_calendar_commitment(db: Session) -> None:
    from app.models import ClinicianCalendarEvent
    from app.services.vms_submission import list_clinician_placements

    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == SAMPLE_DEMO_PORTAL_EMAIL)
        .first()
    )
    if provider is None:
        pytest.skip("demo CNA unavailable")

    before = list_clinician_placements(db, provider.provider_id)
    repaired = repair_demo_portal_placements(db, provider)
    after = list_clinician_placements(db, provider.provider_id)
    has_commitment = (
        db.query(ClinicianCalendarEvent)
        .filter(
            ClinicianCalendarEvent.provider_id == provider.md_license_number,
            ClinicianCalendarEvent.event_type == "SHIFT_COMMITMENT",
        )
        .count()
        > 0
    )
    if has_commitment:
        assert repaired >= 0
        assert len(after) >= len(before)
    else:
        assert repaired == 0
