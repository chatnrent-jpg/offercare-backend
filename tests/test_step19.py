from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas import ClinicianApplyRequest
from app.seed import seed_saint_judes_demo
from app.services.license_verification import apply_as_clinician, is_valid_npi, verify_clinician
from app.services.ops_metrics import get_ops_metrics, list_ops_audit_events
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer


def _make_valid_npi(seed: int) -> str:
    base9 = f"{seed % 1_000_000_000:09d}"
    for check in range(10):
        candidate = f"{base9}{check}"
        if is_valid_npi(candidate):
            return candidate
    raise ValueError("unable to build valid NPI")


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_ops_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/api/ops/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "total_sms_sent" in body
    assert "lock_rate" in body
    assert "audit_events_24h" in body


def test_ops_audit_requires_admin_key(client: TestClient) -> None:
    unauth = TestClient(client.app)
    assert unauth.get("/api/ops/audit").status_code == 401


def test_notify_and_lock_create_audit_events(db: Session) -> None:
    seeded = seed_saint_judes_demo(db)
    offer_id = uuid.UUID(seeded["offer_id"])

    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)
    lock = lock_shift_from_sms_reply(db, from_phone="+14105550001", message_body="YES")
    assert lock.status == "locked"

    recent_types = {row.event_type for row in list_ops_audit_events(db, limit=20)}
    assert "SHIFT_NOTIFY" in recent_types
    assert "SHIFT_LOCK" in recent_types


def test_verify_creates_audit_event(db: Session) -> None:
    token = uuid.uuid4().hex[:6]
    seed = int(token, 16)
    payload = ClinicianApplyRequest(
        full_name="Audit Nurse",
        email=f"audit.{token}@offercare.demo",
        phone_number=f"410{seed % 10_000_000:07d}",
        npi_number=_make_valid_npi(seed),
        md_license_number=f"RN-MD-{token.upper()}",
        min_hourly_rate=95.0,
    )
    provider, _ = apply_as_clinician(db, payload)

    verify_clinician(db, provider.provider_id, action="VERIFY", reviewer="ops_admin")
    events = list_ops_audit_events(db, limit=50)
    assert any(
        row.event_type == "CLINICIAN_VERIFY" and row.entity_id == provider.provider_id
        for row in events
    )


def test_get_ops_metrics_service(db: Session) -> None:
    metrics = get_ops_metrics(db)
    assert metrics["total_sms_sent"] >= 0
    assert 0.0 <= metrics["lock_rate"] <= 1.0


def test_admin_dashboard_includes_audit_panel(client: TestClient) -> None:
    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Audit log" in response.text
    assert "Ops metrics" in response.text
