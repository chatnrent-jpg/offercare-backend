from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import LicenseVerificationLog, MarylandProvider
from app.services.care_taxonomy import synthetic_npi_for_caregiver
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.sms_compliance import (
    SMS_HELP_MESSAGE,
    SMS_STOP_CONFIRMATION,
    classify_inbound_sms,
    provider_is_sms_opted_out,
)
from app.services.worker_consent import WORKER_CONSENT_VERSION, provider_has_sms_dispatch_consent, record_apply_consents


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_classify_inbound_sms_keywords() -> None:
    assert classify_inbound_sms("stop") == "STOP"
    assert classify_inbound_sms("HELP") == "HELP"
    assert classify_inbound_sms("start") == "START"
    assert classify_inbound_sms("YES") == "LOCK"


def test_stop_opt_out_blocks_dispatch(db: Session) -> None:
    email = f"sms.stop.{uuid4().hex[:8]}@example.com"
    provider = MarylandProvider(
        full_name="SMS Stop CNA",
        email=email,
        phone_number=f"410562{uuid4().hex[:4]}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"CNA-MD-{uuid4().hex[:8].upper()}",
        credential_type="CNA",
        min_hourly_rate=22.0,
        license_status="VERIFIED",
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    record_apply_consents(db, provider.provider_id, consent_version=WORKER_CONSENT_VERSION, commit=True)
    assert provider_has_sms_dispatch_consent(db, provider.provider_id) is True

    result = lock_shift_from_sms_reply(db, from_phone=provider.phone_number, message_body="STOP")
    assert result.status == "opted_out"
    assert result.message == SMS_STOP_CONFIRMATION
    db.refresh(provider)
    assert provider_is_sms_opted_out(provider)
    assert provider_has_sms_dispatch_consent(db, provider.provider_id, provider=provider) is False

    opt_row = (
        db.query(LicenseVerificationLog)
        .filter(
            LicenseVerificationLog.provider_id == provider.provider_id,
            LicenseVerificationLog.event_type == "SMS_OPT_OUT",
        )
        .one()
    )
    assert opt_row.check_result == "PASS"


def test_help_returns_help_message(db: Session) -> None:
    email = f"sms.help.{uuid4().hex[:8]}@example.com"
    provider = MarylandProvider(
        full_name="SMS Help CNA",
        email=email,
        phone_number=f"410563{uuid4().hex[:4]}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"CNA-MD-{uuid4().hex[:8].upper()}",
        credential_type="CNA",
        min_hourly_rate=22.0,
        license_status="VERIFIED",
    )
    db.add(provider)
    db.commit()

    result = lock_shift_from_sms_reply(db, from_phone=provider.phone_number, message_body="HELP")
    assert result.status == "help"
    assert result.message == SMS_HELP_MESSAGE


def test_start_re_enables_sms(db: Session) -> None:
    email = f"sms.start.{uuid4().hex[:8]}@example.com"
    provider = MarylandProvider(
        full_name="SMS Start CNA",
        email=email,
        phone_number=f"410564{uuid4().hex[:4]}",
        npi_number=synthetic_npi_for_caregiver(email),
        md_license_number=f"CNA-MD-{uuid4().hex[:8].upper()}",
        credential_type="CNA",
        min_hourly_rate=22.0,
        license_status="VERIFIED",
        sms_opt_out="true",
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    record_apply_consents(db, provider.provider_id, consent_version=WORKER_CONSENT_VERSION, commit=True)

    result = lock_shift_from_sms_reply(db, from_phone=provider.phone_number, message_body="START")
    assert result.status == "opted_in"
    db.refresh(provider)
    assert not provider_is_sms_opted_out(provider)
    assert provider_has_sms_dispatch_consent(db, provider.provider_id, provider=provider) is True
