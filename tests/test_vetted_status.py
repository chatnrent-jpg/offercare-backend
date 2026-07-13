"""Tests for VettedMe credential safety status engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.compliance_monitor import seed_default_compliance_documents
from app.services.vetted_status import (
    VETTED_ACTION_NEEDED,
    VETTED_BLOCKED,
    VETTED_CLEAR,
    VETTED_EXPIRING,
    compute_vetted_status,
)


def _create_provider(db: Session) -> MarylandProvider:
    token = uuid4().hex[:10].upper()
    email = f"vetted.{token.lower()}@example.com"
    digits = "".join(ch for ch in token if ch.isdigit())[-10:].rjust(10, "8")
    provider = MarylandProvider(
        full_name="Vetted Test RN",
        email=email,
        phone_number=f"+1{digits}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"RN{token}",
        state="MD",
        credential_type="RN",
        service_lines="HOSPITAL",
        license_status="UNVERIFIED",
        min_hourly_rate=40.0,
        response_propensity=0.8,
        fatigue_score=0.0,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def test_unverified_provider_is_action_needed() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        assert compute_vetted_status(db, provider) == VETTED_ACTION_NEEDED
    finally:
        db.close()


def test_verified_provider_with_documents_is_clear() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        provider.license_status = "VERIFIED"
        seed_default_compliance_documents(db, provider)
        db.commit()
        assert compute_vetted_status(db, provider) == VETTED_CLEAR
    finally:
        db.close()


def test_expiring_document_marks_expiring() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        provider.license_status = "VERIFIED"
        now = datetime.now(timezone.utc)
        rows = seed_default_compliance_documents(db, provider)
        rows[0].expires_on = now + timedelta(days=7)
        db.commit()
        assert compute_vetted_status(db, provider) == VETTED_EXPIRING
    finally:
        db.close()


def test_expired_license_is_blocked() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        provider.license_status = "EXPIRED"
        seed_default_compliance_documents(db, provider)
        db.commit()
        assert compute_vetted_status(db, provider) == VETTED_BLOCKED
    finally:
        db.close()


def test_vettedme_dashboard_endpoint(client: TestClient) -> None:
    response = client.get("/api/vettedme/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["safety_first"] is True
    assert "status_counts" in body
    assert body["manus_webhook"] == "/api/vettedme/manus/run"
