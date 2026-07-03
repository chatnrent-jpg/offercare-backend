from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.middleware.compliance_sentinel import (
    COMPLIANCE_SENTINEL_BLOCKED,
    COMPLIANCE_SENTINEL_CLEAR,
    COMPLIANCE_SENTINEL_MATCHING_HOLD,
    REASON_HB1106_CONSENT_MISSING,
    REASON_MBON_VERIFICATION_STALE,
    evaluate_compliance_sentinel,
    is_nursing_home_shift,
    record_hb1106_consent_event,
    resolve_mbon_verification_timestamp,
)
from app.models import MdProviderCompliance, MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver


def _unique_phone() -> str:
    return f"+1{uuid4().int % 10**10:010d}"


def _create_provider(db: Session) -> MarylandProvider:
    token = uuid4().hex[:8].upper()
    license_number = f"CNASENT{token}"
    email = f"sentinel.{token.lower()}@example.com"
    provider = MarylandProvider(
        full_name=f"Sentinel Test {token}",
        email=email,
        phone_number=_unique_phone(),
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=license_number,
        state="MD",
        credential_type="CNA",
        service_lines="NURSING_HOME",
        license_status="VERIFIED",
        min_hourly_rate=25.0,
        response_propensity=0.8,
        fatigue_score=0.0,
        last_verified_timestamp=datetime.now(timezone.utc),
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _seed_fresh_mbon(db: Session, provider: MarylandProvider) -> None:
    row = MdProviderCompliance(
        provider_id=provider.provider_id,
        credential_type="CNA",
        license_number=provider.md_license_number,
        compliance_status="COMPLIANT",
        mbon_status_last_checked=datetime.now(timezone.utc),
        mbon_last_status="ACTIVE",
    )
    db.add(row)
    db.commit()


def test_is_nursing_home_shift_recognizes_snf_aliases() -> None:
    assert is_nursing_home_shift(facility_type="SNF")
    assert is_nursing_home_shift(facility_type="NURSING_HOME")
    assert not is_nursing_home_shift(facility_type="HOSPITAL")


def test_sentinel_blocks_missing_hb1106_consent() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        _seed_fresh_mbon(db, provider)
        verdict = evaluate_compliance_sentinel(
            db,
            provider.provider_id,
            facility_type="SNF",
            shift_id="offer-sentinel-001",
            persist_audit=True,
        )
        assert verdict.allowed is False
        assert verdict.matching_hold is True
        assert verdict.compliance_status == COMPLIANCE_SENTINEL_MATCHING_HOLD
        assert REASON_HB1106_CONSENT_MISSING in verdict.reasons

        from sqlalchemy import text

        ledger_count = db.execute(
            text(
                "SELECT COUNT(*) FROM compliance_audit_ledger "
                "WHERE provider_id = :provider_id AND compliance_status = :status"
            ),
            {
                "provider_id": str(provider.provider_id),
                "status": COMPLIANCE_SENTINEL_MATCHING_HOLD,
            },
        ).scalar_one()
        assert int(ledger_count) >= 1
    finally:
        db.close()


def test_sentinel_blocks_stale_mbon_even_with_consent() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        stale_checked_at = datetime.now(timezone.utc) - timedelta(hours=30)
        row = MdProviderCompliance(
            provider_id=provider.provider_id,
            credential_type="CNA",
            license_number=provider.md_license_number,
            compliance_status="COMPLIANT",
            mbon_status_last_checked=stale_checked_at,
            mbon_last_status="ACTIVE",
        )
        db.add(row)
        record_hb1106_consent_event(db, provider.provider_id, commit=True)

        verdict = evaluate_compliance_sentinel(
            db,
            provider.provider_id,
            facility_type="NURSING_HOME",
            persist_audit=False,
        )
        assert verdict.allowed is False
        assert verdict.blocked is True
        assert verdict.compliance_status == COMPLIANCE_SENTINEL_BLOCKED
        assert REASON_MBON_VERIFICATION_STALE in verdict.reasons
        assert verdict.mbon_verification_age_hours is not None
        assert verdict.mbon_verification_age_hours > 24
    finally:
        db.close()


def test_sentinel_clears_when_consent_and_fresh_mbon() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        _seed_fresh_mbon(db, provider)
        record_hb1106_consent_event(db, provider.provider_id, commit=True)

        verdict = evaluate_compliance_sentinel(
            db,
            provider.provider_id,
            facility_type="SNF",
            persist_audit=False,
        )
        assert verdict.allowed is True
        assert verdict.compliance_status == COMPLIANCE_SENTINEL_CLEAR
        assert verdict.reasons == ()
    finally:
        db.close()


def test_sentinel_skips_non_nursing_home_shifts() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        verdict = evaluate_compliance_sentinel(
            db,
            provider.provider_id,
            facility_type="HOSPITAL",
            persist_audit=False,
        )
        assert verdict.allowed is True
        assert verdict.compliance_status == COMPLIANCE_SENTINEL_CLEAR
    finally:
        db.close()


def test_resolve_mbon_verification_timestamp_prefers_compliance_row() -> None:
    db = SessionLocal()
    try:
        provider = _create_provider(db)
        checked_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        db.add(
            MdProviderCompliance(
                provider_id=provider.provider_id,
                credential_type="CNA",
                license_number=provider.md_license_number,
                compliance_status="COMPLIANT",
                mbon_status_last_checked=checked_at,
                mbon_last_status="ACTIVE",
            )
        )
        db.commit()
        resolved = resolve_mbon_verification_timestamp(db, provider.provider_id)
        assert resolved == checked_at
    finally:
        db.close()
