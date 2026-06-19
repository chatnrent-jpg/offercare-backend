"""Sequential SMS cascade — notify next ranked clinician after timeout."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import OfferCareJobOffer, ShiftNotificationLog
from app.schemas import RankedProviderOut, SmsDeliveryOut
from app.services.shift_ranking import (
    _notify_email_for_clinician,
    _notify_push_for_clinician,
    notify_single_ranked_clinician,
    rank_offer_from_db,
    _provider_lookup,
)
from app.services.shift_schedule import resolve_offer_shift_window
from app.services.ops_metrics import log_ops_event


@dataclass(frozen=True)
class CascadeRecipient:
    provider_id: UUID
    full_name: str
    phone_number: str
    rank: int
    notified_at: datetime | None = None


@dataclass(frozen=True)
class CascadeStatus:
    offer_id: UUID
    offer_status: str
    cascade_enabled: bool
    timeout_seconds: int
    notified_count: int
    max_recipients: int
    last_notified_at: datetime | None
    next_eligible_at: datetime | None
    seconds_until_eligible: int
    notified: list[CascadeRecipient]
    next_candidate: CascadeRecipient | None
    can_advance: bool


@dataclass(frozen=True)
class CascadeAdvanceResult:
    status: str
    message: str
    delivery: SmsDeliveryOut | None
    cascade: CascadeStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _notification_logs(db: Session, offer_id: UUID, *, wave_id: UUID | None) -> list[ShiftNotificationLog]:
    query = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.offer_id == offer_id)
        .order_by(ShiftNotificationLog.sent_at.asc())
    )
    if wave_id is None:
        return query.all()
    return query.filter(ShiftNotificationLog.broadcast_wave_id == wave_id).all()


def get_cascade_status(db: Session, offer_id: UUID) -> CascadeStatus:
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        raise ValueError("offer_not_found")

    ranking = rank_offer_from_db(db, offer_id)
    rank_lookup = {row.provider_id: row for row in ranking.ranked}
    logs = _notification_logs(db, offer_id, wave_id=offer.broadcast_wave_id)
    notified_ids: list[UUID] = []
    notified: list[CascadeRecipient] = []
    for log in logs:
        if log.provider_id in notified_ids:
            continue
        notified_ids.append(log.provider_id)
        ranked = rank_lookup.get(log.provider_id)
        notified.append(
            CascadeRecipient(
                provider_id=log.provider_id,
                full_name=ranked.full_name if ranked else str(log.provider_id),
                phone_number=ranked.phone_number if ranked else "",
                rank=ranked.rank if ranked else 0,
                notified_at=_as_utc(log.sent_at),
            )
        )

    last_notified_at = notified[-1].notified_at if notified else None
    timeout = settings.SNIPER_CASCADE_TIMEOUT_SECONDS
    next_eligible_at = None
    seconds_until_eligible = 0
    if last_notified_at is not None:
        next_eligible_at = last_notified_at + timedelta(seconds=timeout)
        seconds_until_eligible = max(0, int((next_eligible_at - _utcnow()).total_seconds()))

    next_candidate = None
    for ranked_row in ranking.ranked:
        if ranked_row.provider_id not in notified_ids:
            next_candidate = CascadeRecipient(
                provider_id=ranked_row.provider_id,
                full_name=ranked_row.full_name,
                phone_number=ranked_row.phone_number,
                rank=ranked_row.rank,
            )
            break

    offer_status = str(offer.compliance_lock_status or "").upper()
    cascade_enabled = settings.SNIPER_CASCADE_ENABLED
    max_recipients = settings.SNIPER_CASCADE_MAX_RECIPIENTS
    can_advance = (
        cascade_enabled
        and offer_status == "BROADCASTING"
        and next_candidate is not None
        and len(notified) < max_recipients
        and seconds_until_eligible == 0
    )

    return CascadeStatus(
        offer_id=offer_id,
        offer_status=offer_status,
        cascade_enabled=cascade_enabled,
        timeout_seconds=timeout,
        notified_count=len(notified),
        max_recipients=max_recipients,
        last_notified_at=last_notified_at,
        next_eligible_at=next_eligible_at,
        seconds_until_eligible=seconds_until_eligible,
        notified=notified,
        next_candidate=next_candidate,
        can_advance=can_advance,
    )


def advance_cascade(
    db: Session,
    offer_id: UUID,
    *,
    reply_keyword: str = "YES",
    force: bool = False,
    actor: str = "shift_sniper",
) -> CascadeAdvanceResult:
    if not settings.SNIPER_CASCADE_ENABLED:
        cascade = get_cascade_status(db, offer_id)
        return CascadeAdvanceResult(
            status="disabled",
            message="Cascade notify is disabled.",
            delivery=None,
            cascade=cascade,
        )

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        raise ValueError("offer_not_found")

    cascade = get_cascade_status(db, offer_id)
    if cascade.offer_status == "LOCKED":
        return CascadeAdvanceResult(
            status="already_locked",
            message="Shift already locked.",
            delivery=None,
            cascade=cascade,
        )
    if cascade.offer_status != "BROADCASTING":
        return CascadeAdvanceResult(
            status="not_broadcasting",
            message="Offer is not in BROADCASTING state. Run notify first.",
            delivery=None,
            cascade=cascade,
        )
    if cascade.next_candidate is None:
        return CascadeAdvanceResult(
            status="exhausted",
            message="No more ranked clinicians to notify for this offer.",
            delivery=None,
            cascade=cascade,
        )
    if cascade.notified_count >= cascade.max_recipients:
        return CascadeAdvanceResult(
            status="exhausted",
            message="Cascade recipient limit reached.",
            delivery=None,
            cascade=cascade,
        )
    if not force and cascade.seconds_until_eligible > 0:
        return CascadeAdvanceResult(
            status="too_early",
            message=f"Wait {cascade.seconds_until_eligible}s before notifying the next clinician.",
            delivery=None,
            cascade=cascade,
        )

    ranking = rank_offer_from_db(db, offer_id)
    ranked_row = next(
        row for row in ranking.ranked if row.provider_id == cascade.next_candidate.provider_id
    )
    shift_starts_at, shift_ends_at = resolve_offer_shift_window(offer)
    delivery = notify_single_ranked_clinician(
        db,
        offer_id,
        ranked_row,
        facility_name=ranking.facility_name,
        shift_role=ranking.shift_role,
        hourly_pay_rate=ranking.hourly_pay_rate,
        reply_keyword=reply_keyword,
        shift_starts_at=shift_starts_at,
        shift_ends_at=shift_ends_at,
        broadcast_wave_id=offer.broadcast_wave_id,
        commit=False,
    )
    provider_lookup = _provider_lookup(db)
    provider = provider_lookup.get(str(ranked_row.provider_id))
    if provider is not None:
        _notify_email_for_clinician(
            db,
            offer_id=offer_id,
            provider=provider,
            facility_name=ranking.facility_name,
            shift_role=ranking.shift_role,
            hourly_pay_rate=ranking.hourly_pay_rate,
            reply_keyword=reply_keyword,
            shift_starts_at=shift_starts_at,
            shift_ends_at=shift_ends_at,
            broadcast_wave_id=offer.broadcast_wave_id,
            commit=False,
        )
        _notify_push_for_clinician(
            db,
            offer_id=offer_id,
            provider=provider,
            facility_name=ranking.facility_name,
            shift_role=ranking.shift_role,
            hourly_pay_rate=ranking.hourly_pay_rate,
            reply_keyword=reply_keyword,
            shift_starts_at=shift_starts_at,
            shift_ends_at=shift_ends_at,
            broadcast_wave_id=offer.broadcast_wave_id,
            commit=False,
        )
    db.commit()
    log_ops_event(
        db,
        event_type="SHIFT_CASCADE",
        actor=actor,
        entity_type="offer",
        entity_id=offer_id,
        summary=f"Cascade SMS sent to {ranked_row.full_name}",
        metadata={"provider_id": str(ranked_row.provider_id), "rank": ranked_row.rank},
    )
    updated = get_cascade_status(db, offer_id)
    return CascadeAdvanceResult(
        status="advanced",
        message=f"Notified {ranked_row.full_name} (rank #{ranked_row.rank}).",
        delivery=delivery,
        cascade=updated,
    )
