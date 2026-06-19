from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.seed import seed_saint_judes_demo
from app.auth import hash_password
from app.models import ClinicianPortalAccount
from app.services.clinician_auth import create_portal_account
from app.services.shift_calendar import (
    build_ics_calendar,
    open_shifts_to_ics,
    placements_to_ics,
)
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer
from app.services.vms_submission import list_clinician_placements


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_build_ics_calendar_contains_vevent() -> None:
    start = datetime(2026, 6, 10, 11, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 10, 23, 0, tzinfo=timezone.utc)
    ics = build_ics_calendar(
        calendar_name="Test",
        events=[
            "BEGIN:VEVENT\r\nUID:test@offercare.ai\r\n"
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}\r\n"
            f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}\r\n"
            "SUMMARY:ICU_RN\r\nEND:VEVENT"
        ],
    )
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics
    assert "END:VCALENDAR" in ics


def test_placements_to_ics_includes_locked_shift(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")

    nurse_a = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "nurse.a@offercare.demo")
        .one()
    )
    rows = list_clinician_placements(db, nurse_a.provider_id, limit=10)
    assert rows
    ics = placements_to_ics(rows)
    assert "Saint Jude" in ics
    assert "BEGIN:VEVENT" in ics
    assert "STATUS:CONFIRMED" in ics


def test_open_shifts_calendar_endpoint(client: TestClient) -> None:
    client.post("/api/seed/saint-judes")
    response = client.get("/api/shifts/open/calendar.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "ICU_RN" in response.text
    assert "STATUS:TENTATIVE" in response.text


def test_clinician_placement_calendar_requires_auth(client: TestClient) -> None:
    assert client.get("/api/clinicians/me/calendar.ics").status_code == 401


def _ensure_portal_password(db: Session, provider_id: UUID, password: str) -> None:
    account = (
        db.query(ClinicianPortalAccount)
        .filter(ClinicianPortalAccount.provider_id == provider_id)
        .first()
    )
    if account is None:
        create_portal_account(db, provider_id, password)
        return
    account.password_hash = hash_password(password)
    db.commit()


def test_clinician_placement_calendar_after_lock(db: Session, client: TestClient) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    nurse_a = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email == "nurse.a@offercare.demo")
        .one()
    )
    _ensure_portal_password(db, nurse_a.provider_id, "SecretPass1")
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")

    login_resp = client.post(
        "/api/clinicians/login",
        json={"email": "nurse.a@offercare.demo", "password": "SecretPass1"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    response = client.get(
        "/api/clinicians/me/calendar.ics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "placement-" in response.text
    assert "Saint Jude" in response.text


def test_open_shifts_to_ics_respects_county_filter(db: Session) -> None:
    from app.services.shift_offer_generator import list_open_shifts

    rows = list_open_shifts(db, county="Baltimore", limit=5)
    ics = open_shifts_to_ics(rows)
    assert "BEGIN:VCALENDAR" in ics
    if rows:
        assert rows[0]["facility_name"] in ics


def test_portal_documents_calendar_buttons(client: TestClient) -> None:
    response = client.get("/portal/")
    assert response.status_code == 200
    assert "Download my calendar" in response.text
    assert "Download matched shifts" in response.text
    assert 'rel="manifest"' in response.text
