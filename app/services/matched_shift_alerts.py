"""Push alerts for clinicians whose profile matches a new open shift."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandProvider, OfferCareJobOffer, ShiftNotificationLog
from app.services.push_alerts import build_matched_shift_alert_push, send_shift_push
from app.services.push_subscriptions import list_push_subscriptions_for_provider, touch_push_subscription
from app.services.shift_matching import provider_matches_open_shift
from app.services.shift_offer_generator import get_open_shift_by_id
from app.services.shift_schedule import format_shift_window_et, resolve_offer_shift_window
from app.services.sniper_learning import refresh_provider_sniper_scores
from app.services.states import normalize_state


def list_matched_providers_for_offer(db: Session, offer_id: UUID) -> list[MarylandProvider]:
    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        return []
    if str(row["compliance_lock_status"]).upper() != "BROADCASTING":
        return []

    facility_state = normalize_state(str(row["state"]))
    providers = (
        db.query(MarylandProvider)
        .filter(
            MarylandProvider.state == facility_state,
            MarylandProvider.license_status == "VERIFIED",
        )
        .all()
    )
    matched: list[MarylandProvider] = []
    for provider in providers:
        if not provider_matches_open_shift(db, provider, row):
            continue
        if not list_push_subscriptions_for_provider(db, provider.provider_id):
            continue
        matched.append(provider)
    return matched


def notify_matched_clinicians_for_offer(
    db: Session,
    offer_id: UUID,
    *,
    commit: bool = True,
) -> int:
    if not settings.PUSH_ALERTS_ENABLED or not settings.MATCHED_SHIFT_PUSH_ON_AUTO_CREATE:
        return 0

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        return 0

    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        return 0

    shift_starts_at, shift_ends_at = resolve_offer_shift_window(offer)
    schedule_line = ""
    if shift_starts_at is not None and shift_ends_at is not None:
        schedule_line = f" · {format_shift_window_et(shift_starts_at, shift_ends_at)}"

    title, body = build_matched_shift_alert_push(
        facility_name=str(row["facility_name"]),
        shift_role=str(row["shift_role"]),
        hourly_pay_rate=float(row["hourly_pay_rate"]),
        schedule_line=schedule_line,
    )

    sent = 0
    for provider in list_matched_providers_for_offer(db, offer_id):
        for subscription in list_push_subscriptions_for_provider(db, provider.provider_id):
            push = send_shift_push(
                endpoint=subscription.endpoint,
                p256dh_key=subscription.p256dh_key,
                auth_key=subscription.auth_key,
                title=title,
                message_body=body,
                data={"offer_id": str(offer_id), "alert_type": "matched_shift"},
            )
            if push.status == "SKIPPED":
                continue
            touch_push_subscription(db, subscription)
            db.add(
                ShiftNotificationLog(
                    offer_id=offer_id,
                    provider_id=provider.provider_id,
                    channel="MATCHED_PUSH",
                    status=push.status,
                    message_body=body,
                )
            )
            sent += 1
        refresh_provider_sniper_scores(db, provider.provider_id, commit=False)

    if sent and commit:
        db.commit()
    return sent


def notify_matched_clinicians_for_offers(db: Session, offer_ids: list[UUID]) -> int:
    total = 0
    for offer_id in offer_ids:
        total += notify_matched_clinicians_for_offer(db, offer_id, commit=False)
    if total:
        db.commit()
    return total
