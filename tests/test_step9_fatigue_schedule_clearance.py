from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from strategy.schedule_conflict_validator import ScheduleConflictValidator


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_provider(db: Session, *, fatigue_score: float) -> MarylandProvider:
    token = uuid.uuid4().hex[:6]
    provider = MarylandProvider(
        full_name=f"Fatigue Cap {token}",
        email=f"fatigue.cap.{token}@offercare.demo",
        phone_number=f"+1410{int(token, 16) % 10_000_000:07d}",
        npi_number=synthetic_npi_for_caregiver(f"fatigue.cap.{token}@offercare.demo"),
        md_license_number=f"CNA-MD-FTG{token.upper()}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=20.0,
        response_propensity=0.8,
        fatigue_score=fatigue_score,
    )
    db.add(provider)
    db.flush()
    return provider


def test_fatigue_hard_block_prevents_schedule_clearance(db: Session) -> None:
    provider = _make_provider(db, fatigue_score=4.5)
    db.commit()
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=8)
    validator = ScheduleConflictValidator(db=db)
    try:
        clearance = validator.evaluate_schedule_clearance(
            provider.md_license_number,
            start,
            end,
        )
    finally:
        validator.close()

    assert clearance["has_conflict"] is True
    assert clearance["conflict_type"] == "FATIGUE_CAP_EXCEEDED"
    assert float(clearance["fatigue_score"]) == 4.5


def test_fatigue_soft_warn_allows_schedule_clearance(db: Session) -> None:
    provider = _make_provider(db, fatigue_score=3.0)
    db.commit()
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=8)
    validator = ScheduleConflictValidator(db=db)
    try:
        clearance = validator.evaluate_schedule_clearance(
            provider.md_license_number,
            start,
            end,
        )
    finally:
        validator.close()

    assert clearance["has_conflict"] is False
    assert clearance["conflict_type"] == "FATIGUE_ELEVATED"
    assert float(clearance["fatigue_score"]) == 3.0


def test_low_fatigue_remains_clear(db: Session) -> None:
    provider = _make_provider(db, fatigue_score=0.5)
    db.commit()
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=8)
    validator = ScheduleConflictValidator(db=db)
    try:
        clearance = validator.evaluate_schedule_clearance(
            provider.md_license_number,
            start,
            end,
        )
    finally:
        validator.close()

    assert clearance["has_conflict"] is False
    assert clearance["conflict_type"] == "CLEAR"


def test_ops_console_documents_fatigue_clearance_states() -> None:
    from pathlib import Path

    text = Path("ui_dashboard/ops_console.py").read_text(encoding="utf-8")
    assert "FATIGUE_ELEVATED" in text
    assert "FATIGUE_CAP_EXCEEDED" in text
