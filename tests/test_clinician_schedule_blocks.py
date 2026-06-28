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
from strategy.clinician_calendar_writer import ClinicianCalendarWriter
from strategy.schedule_conflict_validator import ScheduleConflictValidator


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
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_provider(db: Session) -> MarylandProvider:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Schedule Block {token}",
        email=f"schedule.block.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"schedule.block.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-BLK{token.upper()}",
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
    return provider


def test_create_and_delete_schedule_block(client: TestClient, db: Session) -> None:
    provider = _make_provider(db)
    headers = _auth_headers(client, db, provider)
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=8)

    create_resp = client.post(
        "/api/clinicians/me/schedule/blocks",
        headers=headers,
        json={
            "event_type": "BLACKOUT_UNAVAILABLE",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body["event_type"] == "BLACKOUT_UNAVAILABLE"
    event_id = body["event_id"]

    listed = client.get("/api/clinicians/me/schedule", headers=headers)
    assert listed.status_code == 200
    assert any(row["event_id"] == event_id for row in listed.json()["events"])

    delete_resp = client.delete(f"/api/clinicians/me/schedule/blocks/{event_id}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["event_id"] == event_id


def test_blackout_conflicts_with_shift_commitment(client: TestClient, db: Session) -> None:
    provider = _make_provider(db)
    headers = _auth_headers(client, db, provider)
    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=8)

    writer = ClinicianCalendarWriter(db)
    writer.record_shift_commitment(
        provider=provider,
        offer=type(
            "Offer",
            (),
            {
                "offer_id": uuid.uuid4(),
                "shift_starts_at": start,
                "shift_ends_at": end,
                "shift_role": "CNA",
                "compliance_lock_status": "LOCKED",
            },
        )(),
        facility=type("Facility", (), {"name": "Test SNF", "facility_id": uuid.uuid4()})(),
        channel="test",
        placement_id=None,
    )
    db.commit()

    create_resp = client.post(
        "/api/clinicians/me/schedule/blocks",
        headers=headers,
        json={
            "event_type": "BLACKOUT_UNAVAILABLE",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert create_resp.status_code == 409
    assert create_resp.json()["detail"] == "schedule_conflict"


def test_soft_block_does_not_hard_block_clearance(db: Session) -> None:
    provider = _make_provider(db)
    start = datetime.now(timezone.utc) + timedelta(days=4)
    end = start + timedelta(hours=4)

    writer = ClinicianCalendarWriter(db)
    writer.record_availability_block(
        provider=provider,
        event_type="SOFT_BLOCK_PREFERENCE",
        start_time=start,
        end_time=end,
    )
    db.commit()

    validator = ScheduleConflictValidator(db=db)
    try:
        probe_start = start + timedelta(hours=1)
        probe_end = probe_start + timedelta(hours=1)
        clearance = validator.evaluate_schedule_clearance(
            provider.md_license_number,
            probe_start,
            probe_end,
        )
    finally:
        validator.close()

    assert clearance["conflict_type"] == "SOFT_PREFERENCE_HIT"
    assert clearance["has_conflict"] is False
