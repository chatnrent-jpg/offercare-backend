from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.middleware.compliance_sentinel import (
    COMPLIANCE_SENTINEL_CLEAR,
    REASON_HB1106_CONSENT_MISSING,
    evaluate_compliance_sentinel,
)
from app.models import LicenseVerificationLog, MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.worker_consent import (
    WORKER_CONSENT_VERSION,
    record_maryland_aedt_consent,
    resolve_provider_consent_signed_at,
)


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _provider(db: Session) -> MarylandProvider:
    token = uuid4().hex[:8].upper()
    email = f"aedt.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=f"AEDT Test {token}",
        email=email,
        phone_number=f"410555{int(token[:4], 16) % 10000:04d}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"CNA-AEDT-{token}",
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=25.0,
        last_verified_timestamp=datetime.now(timezone.utc),
    )
    db.add(provider)
    db.flush()
    return provider


def test_record_maryland_aedt_consent_sets_profile_timestamp(db: Session) -> None:
    provider = _provider(db)
    signed_at = record_maryland_aedt_consent(
        db,
        provider.provider_id,
        consent_version=WORKER_CONSENT_VERSION,
        client_ip="127.0.0.1",
    )
    db.flush()
    db.refresh(provider)

    assert provider.consent_signed_at is not None
    assert resolve_provider_consent_signed_at(db, provider.provider_id) == signed_at
    events = {
        row.event_type
        for row in db.query(LicenseVerificationLog)
        .filter(LicenseVerificationLog.provider_id == provider.provider_id)
        .all()
    }
    assert "CONSENT_MARYLAND_AEDT_30_DAY" in events
    assert "CONSENT_HB1106_ANTI_BIAS" in events


def test_compliance_sentinel_clears_when_consent_signed_at_present(db: Session) -> None:
    provider = _provider(db)
    record_maryland_aedt_consent(
        db,
        provider.provider_id,
        consent_version=WORKER_CONSENT_VERSION,
    )
    db.flush()

    verdict = evaluate_compliance_sentinel(
        db,
        provider.provider_id,
        facility_type="SNF",
        persist_audit=False,
    )
    assert verdict.compliance_status == COMPLIANCE_SENTINEL_CLEAR
    assert verdict.hb1106_consent_signed_at is not None
    assert REASON_HB1106_CONSENT_MISSING not in verdict.reasons
