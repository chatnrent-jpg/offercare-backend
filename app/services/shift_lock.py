"""Lock shifts when clinicians reply YES via SMS."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ClinicalPlacementLedger,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
    ShiftNotificationLog,
)
from app.services.sniper_learning import refresh_provider_sniper_scores
from app.services.ops_metrics import log_ops_event


@dataclass(frozen=True)
class ShiftLockResult:
    status: str
    message: str
    offer_id: UUID | None = None
    provider_id: UUID | None = None
    placement_id: UUID | None = None


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if str(phone or "").startswith("+"):
        return str(phone).strip()
    return f"+{digits}" if digits else ""


def is_lock_keyword(body: str, keyword: str | None = None) -> bool:
    token = str(keyword or settings.TWILIO_REPLY_KEYWORD or "YES").strip().upper()
    return str(body or "").strip().upper() == token


def _compliance_token(provider: MarylandProvider) -> str:
    raw = f"{provider.md_license_number}:{provider.license_status}:{provider.npi_number}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _finalize_shift_lock(
    db: Session,
    *,
    provider: MarylandProvider,
    offer: OfferCareJobOffer,
    channel: str,
) -> ShiftLockResult:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == offer.facility_id)
        .first()
    )
    facility_name = facility.name if facility else "Maryland facility"

    offer.compliance_lock_status = "LOCKED"
    offer.assigned_provider_id = provider.provider_id

    placement = ClinicalPlacementLedger(
        offer_id=offer.offer_id,
        facility_name=facility_name,
        clinical_unit=offer.shift_role,
        hourly_bill_rate=offer.hourly_pay_rate,
        assigned_clinician_id=provider.provider_id,
        compliance_snapshot_token=_compliance_token(provider),
        vms_submission_status="PENDING",
    )
    db.add(placement)
    db.commit()
    db.refresh(placement)
    refresh_provider_sniper_scores(db, provider.provider_id)
    log_ops_event(
        db,
        event_type="SHIFT_LOCK",
        actor=provider.full_name,
        entity_type="offer",
        entity_id=offer.offer_id,
        summary=f"Shift locked by {provider.full_name} via {channel}",
        metadata={
            "provider_id": str(provider.provider_id),
            "placement_id": str(placement.placement_id),
            "channel": channel,
        },
    )

    return ShiftLockResult(
        status="locked",
        message=f"Shift locked at {facility_name}. You're confirmed for {offer.shift_role}.",
        offer_id=offer.offer_id,
        provider_id=provider.provider_id,
        placement_id=placement.placement_id,
    )


def _find_provider_by_phone(db: Session, phone: str) -> MarylandProvider | None:
    target = normalize_phone(phone)
    target_digits = re.sub(r"\D", "", target)
    for provider in db.query(MarylandProvider).all():
        provider_phone = normalize_phone(provider.phone_number)
        if provider_phone == target:
            return provider
        if re.sub(r"\D", "", provider_phone) == target_digits:
            return provider
    return None


def lock_shift_from_sms_reply(
    db: Session,
    *,
    from_phone: str,
    message_body: str,
    reply_keyword: str | None = None,
) -> ShiftLockResult:
    keyword = reply_keyword or settings.TWILIO_REPLY_KEYWORD
    if not is_lock_keyword(message_body, keyword):
        return ShiftLockResult(
            status="ignored",
            message=f"Reply {keyword} to lock an open shift.",
        )

    provider = _find_provider_by_phone(db, from_phone)
    if provider is None:
        return ShiftLockResult(status="unknown_sender", message="Phone not registered with OfferCare.ai.")

    if str(provider.license_status).upper() != "VERIFIED":
        return ShiftLockResult(
            status="rejected",
            message="Credentials not verified. Complete verification before accepting shifts.",
            provider_id=provider.provider_id,
        )

    notification = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.provider_id == provider.provider_id)
        .order_by(ShiftNotificationLog.sent_at.desc())
        .first()
    )
    if notification is None:
        return ShiftLockResult(
            status="no_open_offer",
            message="No open shift broadcast found for this number.",
            provider_id=provider.provider_id,
        )

    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == notification.offer_id)
        .with_for_update()
        .first()
    )
    if offer is None:
        return ShiftLockResult(
            status="no_open_offer",
            message="No open shift broadcast found for this number.",
            provider_id=provider.provider_id,
        )

    if str(offer.compliance_lock_status) != "BROADCASTING":
        return ShiftLockResult(
            status="already_locked",
            message="This shift was already locked by another clinician.",
            offer_id=offer.offer_id,
            provider_id=provider.provider_id,
        )

    return _finalize_shift_lock(db, provider=provider, offer=offer, channel="sms")


def lock_shift_for_provider(
    db: Session,
    *,
    provider: MarylandProvider,
    offer_id: UUID,
) -> ShiftLockResult:
    if str(provider.license_status).upper() != "VERIFIED":
        return ShiftLockResult(
            status="rejected",
            message="Credentials not verified. Complete verification before accepting shifts.",
            provider_id=provider.provider_id,
        )

    from app.services.shift_matching import get_matched_shift_for_provider

    if get_matched_shift_for_provider(db, provider, offer_id) is None:
        return ShiftLockResult(
            status="not_matched",
            message="This shift does not match your credential, care setting, or minimum pay.",
            provider_id=provider.provider_id,
            offer_id=offer_id,
        )

    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == offer_id)
        .with_for_update()
        .first()
    )
    if offer is None:
        return ShiftLockResult(
            status="not_found",
            message="Shift not found.",
            provider_id=provider.provider_id,
            offer_id=offer_id,
        )

    if str(offer.compliance_lock_status) != "BROADCASTING":
        return ShiftLockResult(
            status="already_locked",
            message="This shift was already locked by another clinician.",
            offer_id=offer.offer_id,
            provider_id=provider.provider_id,
        )

    return _finalize_shift_lock(db, provider=provider, offer=offer, channel="portal")


def twiml_reply(message: str) -> str:
    safe = (
        str(message or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'
