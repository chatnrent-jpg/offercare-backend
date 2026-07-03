"""Lock shifts when clinicians reply YES via SMS."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
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
    facility_name: str | None = None
    shift_role: str | None = None
    shift_starts_at: datetime | None = None
    shift_ends_at: datetime | None = None
    hourly_pay_rate: float | None = None
    provider_license: str | None = None


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


def _offer_lock_context(db: Session, *, provider: MarylandProvider, offer: OfferCareJobOffer) -> dict:
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == offer.facility_id)
        .first()
    )
    facility_name = facility.name if facility else "Maryland facility"
    return {
        "facility_name": facility_name,
        "shift_role": offer.shift_role,
        "shift_starts_at": offer.shift_starts_at,
        "shift_ends_at": offer.shift_ends_at,
        "hourly_pay_rate": float(offer.hourly_pay_rate) if offer.hourly_pay_rate is not None else None,
        "provider_license": provider.md_license_number,
        "offer_id": offer.offer_id,
        "provider_id": provider.provider_id,
    }


def _schedule_conflict_blocks_lock(
    db: Session,
    *,
    provider: MarylandProvider,
    offer: OfferCareJobOffer,
) -> ShiftLockResult | None:
    try:
        from strategy.clinician_calendar_writer import _provider_calendar_token, _shift_interval_for_offer
        from strategy.schedule_conflict_validator import ScheduleConflictValidator

        start_time, end_time = _shift_interval_for_offer(offer)
        validator = ScheduleConflictValidator(db=db)
        clearance = validator.evaluate_schedule_clearance(
            _provider_calendar_token(provider),
            start_time,
            end_time,
        )
        if clearance.get("has_conflict"):
            conflict_type = str(clearance.get("conflict_type") or "")
            ctx = _offer_lock_context(db, provider=provider, offer=offer)
            if conflict_type == "FATIGUE_CAP_EXCEEDED":
                return ShiftLockResult(
                    status="schedule_conflict",
                    message="Fatigue cap exceeded. Rest before accepting another shift.",
                    **ctx,
                )
            return ShiftLockResult(
                status="schedule_conflict",
                message="Schedule conflict detected. You already have a commitment during this interval.",
                **ctx,
            )
    except Exception as exc:  # noqa: BLE001
        log_ops_event(
            db,
            event_type="SCHEDULE_CLEARANCE_SKIPPED",
            actor=provider.full_name,
            entity_type="offer",
            entity_id=offer.offer_id,
            summary=f"Schedule clearance skipped during lock: {exc}",
            metadata={"provider_id": str(provider.provider_id), "error": str(exc)},
        )
    return None


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
    db.flush()

    from strategy.clinician_calendar_writer import record_shift_commitment_safe

    record_shift_commitment_safe(
        db,
        provider=provider,
        offer=offer,
        facility=facility,
        channel=channel,
        placement_id=placement.placement_id,
    )

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
        placement_id=placement.placement_id,
        **_offer_lock_context(db, provider=provider, offer=offer),
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
    from app.services.sms_compliance import (
        SMS_HELP_MESSAGE,
        SMS_START_CONFIRMATION,
        SMS_STOP_CONFIRMATION,
        classify_inbound_sms,
        opt_in_provider_sms,
        opt_out_provider_sms,
    )

    keyword_action = classify_inbound_sms(message_body)
    provider = _find_provider_by_phone(db, from_phone)

    if keyword_action == "HELP":
        return ShiftLockResult(status="help", message=SMS_HELP_MESSAGE)

    if keyword_action == "STOP":
        if provider is None:
            return ShiftLockResult(
                status="unknown_sender",
                message="Phone not registered with VettedCare.ai.",
            )
        opt_out_provider_sms(db, provider)
        return ShiftLockResult(
            status="opted_out",
            message=SMS_STOP_CONFIRMATION,
            provider_id=provider.provider_id,
        )

    if keyword_action == "START":
        if provider is None:
            return ShiftLockResult(
                status="unknown_sender",
                message="Phone not registered with VettedCare.ai.",
            )
        opt_in_provider_sms(db, provider)
        return ShiftLockResult(
            status="opted_in",
            message=SMS_START_CONFIRMATION,
            provider_id=provider.provider_id,
        )

    lock_kw = reply_keyword or settings.TWILIO_REPLY_KEYWORD
    if not is_lock_keyword(message_body, lock_kw):
        return ShiftLockResult(
            status="ignored",
            message=f"Reply {lock_kw} to lock an open shift, HELP for help, or STOP to opt out.",
        )

    if provider is None:
        return ShiftLockResult(status="unknown_sender", message="Phone not registered with VettedCare.ai.")

    from app.services.sms_compliance import provider_is_sms_opted_out

    if provider_is_sms_opted_out(provider):
        return ShiftLockResult(
            status="opted_out",
            message=SMS_STOP_CONFIRMATION,
            provider_id=provider.provider_id,
        )

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

    conflict = _schedule_conflict_blocks_lock(db, provider=provider, offer=offer)
    if conflict is not None:
        return conflict

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

    conflict = _schedule_conflict_blocks_lock(db, provider=provider, offer=offer)
    if conflict is not None:
        return conflict

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
