"""Portal step 16 — post-lock confirmation modal and ops conflict deep links."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.schemas import ShiftLockResponse
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.clinician_auth import create_portal_account
from app.services.shift_lock import _offer_lock_context
from app.models import OfferCareJobOffer, MarylandFacility


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_shift_lock_response_includes_confirmation_fields() -> None:
    start = datetime(2026, 6, 28, 13, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=8)
    payload = ShiftLockResponse(
        status="locked",
        message="Shift locked at Demo SNF. You're confirmed for CNA.",
        offer_id=uuid.uuid4(),
        provider_id=uuid.uuid4(),
        placement_id=uuid.uuid4(),
        facility_name="Demo SNF",
        shift_role="CNA",
        shift_starts_at=start,
        shift_ends_at=end,
        hourly_pay_rate=24.0,
        provider_license="CNA-NJ-A001",
    )
    assert payload.facility_name == "Demo SNF"
    assert payload.shift_role == "CNA"
    assert payload.hourly_pay_rate == 24.0


def test_offer_lock_context_includes_provider_license(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Lock ctx {token}",
        email=f"lock.ctx.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"lock.ctx.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-CTX{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=20.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    facility = MarylandFacility(
        name=f"Ctx Facility {token}",
        facility_type="NURSING_HOME",
        county="Montgomery County",
        state="MD",
        vms_integration_type="SCRAPE",
    )
    db.add_all([provider, facility])
    db.flush()
    start = datetime.now(timezone.utc) + timedelta(days=1)
    offer = OfferCareJobOffer(
        facility_id=facility.facility_id,
        shift_role="CNA",
        hourly_pay_rate=22.5,
        shift_starts_at=start,
        shift_ends_at=start + timedelta(hours=8),
        compliance_lock_status="BROADCASTING",
    )
    db.add(offer)
    db.flush()
    ctx = _offer_lock_context(db, provider=provider, offer=offer)
    assert ctx["provider_license"] == provider.md_license_number
    assert ctx["facility_name"] == facility.name
    assert ctx["hourly_pay_rate"] == 22.5


def test_portal_step16_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert 'data-portal-build="portal-step16-2026"' in html
    assert "lock-confirm-modal" in html
    assert 'meta name="ops-console-url"' in html
    assert "showLockConfirmModal" in js
    assert "buildOpsConsoleConflictLink" in js
    assert "ops-conflict-link" in js


def test_ops_console_reads_portal_query_params() -> None:
    from pathlib import Path

    text = Path("ui_dashboard/ops_console.py").read_text(encoding="utf-8")
    assert 'st.query_params.get("provider_id")' in text
    assert "shift_start" in text
