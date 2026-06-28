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
from app.services.shift_calendar import unified_clinician_calendar_to_ics
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


def test_unified_calendar_ics_endpoint(client: TestClient, db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Unified ICS {token}",
        email=f"unified.ics.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"unified.ics.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-UICS{token.upper()}",
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

    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=8)
    writer = ClinicianCalendarWriter(db)
    writer.record_availability_block(
        provider=provider,
        event_type="SOFT_BLOCK_PREFERENCE",
        start_time=start,
        end_time=end,
        channel="test",
    )
    db.commit()

    headers = _auth_headers(client, db, provider)
    response = client.get("/api/clinicians/me/unified/calendar.ics", headers=headers)
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "Soft preference block" in response.text


def test_unified_clinician_calendar_to_ics_merges_events() -> None:
    start = datetime(2026, 6, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 28, 16, 0, tzinfo=timezone.utc)
    ics = unified_clinician_calendar_to_ics(
        placements=[
            {
                "placement_id": uuid.uuid4(),
                "clinical_unit": "Med/Surg",
                "facility_name": "Unity Hospital",
                "hourly_bill_rate": 55.0,
                "vms_submission_status": "PENDING",
                "shift_starts_at": start,
                "shift_ends_at": end,
            }
        ],
        schedule_events=[
            {
                "event_id": uuid.uuid4(),
                "event_type": "BLACKOUT_UNAVAILABLE",
                "start_time": start + timedelta(days=1),
                "end_time": end + timedelta(days=1),
            }
        ],
        calendar_token="CNA-TEST",
    )
    assert ics.count("BEGIN:VEVENT") == 2
    assert "Unity Hospital" in ics
    assert "Blackout" in ics


def test_clinician_open_shifts_includes_lock_eligible(client: TestClient, db: Session) -> None:
    provider = db.query(MarylandProvider).filter(MarylandProvider.email == "nj.snf.cna.a@offercare.demo").first()
    if provider is None:
        pytest.skip("demo CNA not seeded")
    headers = _auth_headers(client, db, provider)
    response = client.get("/api/clinicians/me/open-shifts?limit=5", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    if rows:
        assert "lock_eligible" in rows[0]
        assert "lock_preview" in rows[0]
        assert "rate_delta" in rows[0]


def test_portal_step12_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert "download-unified-calendar-btn" in html
    assert "/api/clinicians/me/unified/calendar.ics" in js
    assert "/api/clinicians/me/open-shifts" in js
    assert "showLockError" in js
    assert "lock_eligible" in js
