from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.clinician_auth import create_portal_account
from app.services.shift_calendar import schedule_events_to_ics
from strategy.clinician_calendar_writer import ClinicianCalendarWriter


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _auth_headers(client: TestClient, db: Session, provider: MarylandProvider) -> dict[str, str]:
    create_portal_account(db, provider.provider_id, "SecretPass1")
    db.commit()
    login = client.post(
        "/api/clinicians/login",
        json={"email": provider.email, "password": "SecretPass1"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_schedule_calendar_ics_endpoint(client: TestClient, db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Schedule ICS {token}",
        email=f"schedule.ics.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"schedule.ics.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-ICS{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=20.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.flush()

    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=8)
    writer = ClinicianCalendarWriter(db)
    writer.record_availability_block(
        provider=provider,
        event_type="BLACKOUT_UNAVAILABLE",
        start_time=start,
        end_time=end,
        channel="test",
    )
    db.commit()

    headers = _auth_headers(client, db, provider)
    response = client.get("/api/clinicians/me/schedule/calendar.ics", headers=headers)
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "Blackout" in response.text


def test_schedule_events_to_ics_builds_events() -> None:
    start = datetime(2026, 6, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 28, 16, 0, tzinfo=timezone.utc)
    ics = schedule_events_to_ics(
        [
            {
                "event_id": uuid.uuid4(),
                "event_type": "SHIFT_COMMITMENT",
                "start_time": start,
                "end_time": end,
                "facility_name": "Test SNF",
                "shift_role": "CNA",
            }
        ],
        calendar_token="CNA-MD-TEST",
    )
    assert "BEGIN:VEVENT" in ics
    assert "Test SNF" in ics


def test_portal_schedule_tab_has_ics_download(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert "download-schedule-calendar-btn" in html
    assert "/api/clinicians/me/schedule/calendar.ics" in js


def test_ops_console_shows_vault_fatigue_metrics() -> None:
    from pathlib import Path

    text = Path("ui_dashboard/ops_console.py").read_text(encoding="utf-8")
    assert "_fetch_provider_fatigue_safe" in text
    assert "calendar_vault_fatigue" in text
