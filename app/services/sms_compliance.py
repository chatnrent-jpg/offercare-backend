"""TCPA SMS keyword handling — STOP, START, HELP."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LicenseVerificationLog, MarylandProvider

STOP_KEYWORDS: frozenset[str] = frozenset(
    {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
)
START_KEYWORDS: frozenset[str] = frozenset({"START", "UNSTOP"})
HELP_KEYWORDS: frozenset[str] = frozenset({"HELP", "INFO"})

SMS_HELP_MESSAGE = (
    "VettedCare.ai shift alerts. Reply YES to lock an offered shift. "
    "Reply STOP to opt out. compliance@vettedcare.ai"
)
SMS_STOP_CONFIRMATION = (
    "You are unsubscribed from VettedCare shift-offer texts. Reply START to re-subscribe."
)
SMS_START_CONFIRMATION = (
    "VettedCare shift alerts re-enabled. Reply YES to lock an open shift. Reply STOP to opt out."
)


def normalize_sms_keyword(body: str) -> str:
    token = re.sub(r"\s+", " ", str(body or "").strip().upper())
    token = token.split()[0] if token else ""
    return token


def classify_inbound_sms(body: str) -> str:
    token = normalize_sms_keyword(body)
    if token in STOP_KEYWORDS:
        return "STOP"
    if token in START_KEYWORDS:
        return "START"
    if token in HELP_KEYWORDS:
        return "HELP"
    lock_token = str(settings.TWILIO_REPLY_KEYWORD or "YES").strip().upper()
    if token == lock_token:
        return "LOCK"
    return "OTHER"


def provider_is_sms_opted_out(provider: MarylandProvider) -> bool:
    return str(getattr(provider, "sms_opt_out", "false")).lower() == "true"


def record_sms_compliance_event(
    db: Session,
    provider_id: UUID,
    *,
    event_type: str,
    check_result: str,
    notes: str,
    commit: bool = False,
) -> None:
    db.add(
        LicenseVerificationLog(
            provider_id=provider_id,
            event_type=event_type,
            check_result=check_result,
            notes=notes[:500],
            reviewer="twilio_inbound",
        )
    )
    if commit:
        db.commit()


def opt_out_provider_sms(db: Session, provider: MarylandProvider) -> None:
    provider.sms_opt_out = "true"
    record_sms_compliance_event(
        db,
        provider.provider_id,
        event_type="SMS_OPT_OUT",
        check_result="PASS",
        notes="Inbound STOP keyword received",
    )
    db.commit()


def opt_in_provider_sms(db: Session, provider: MarylandProvider) -> None:
    provider.sms_opt_out = "false"
    record_sms_compliance_event(
        db,
        provider.provider_id,
        event_type="SMS_OPT_IN",
        check_result="PASS",
        notes="Inbound START keyword received",
    )
    db.commit()
