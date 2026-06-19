"""Rank clinicians from PostgreSQL for an open offer."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer, ShiftNotificationLog
from app.schemas import (
    EliminatedProviderOut,
    EmailDeliveryOut,
    NotifyResponse,
    OfferRankResponse,
    PushDeliveryOut,
    RankedProviderOut,
    SmsDeliveryOut,
)
from app.services.care_taxonomy import clinician_qualifies_for_shift_role, credential_valid_in_state, provider_supports_facility_type
from app.services.compliance_monitor import (
    has_active_exclusion,
    has_expired_required_documents,
)
from app.services.geo_matching import _coords, haversine_miles
from app.services.postgis_geo import postgis_geo_ready, query_geo_eligible_provider_ids
from app.services.email_alerts import build_shift_alert_email, send_shift_email
from app.services.push_alerts import build_shift_alert_push, send_shift_push
from app.services.push_subscriptions import list_push_subscriptions_for_provider, touch_push_subscription
from app.services.sms import build_shift_alert_message, send_shift_sms
from app.services.ops_metrics import log_ops_event
from app.services.sniper_learning import refresh_provider_sniper_scores
from app.services.states import normalize_state
from app.services.shift_schedule import format_shift_window_et, resolve_offer_shift_window
from app.shift_sniper import ClinicianCandidate, SniperWeights, placement_probability, rank_clinicians_for_shift


def _weights() -> SniperWeights:
    return SniperWeights(
        compliance=settings.SNIPER_WEIGHT_COMPLIANCE,
        rate_delta=settings.SNIPER_WEIGHT_RATE_DELTA,
        response_propensity=settings.SNIPER_WEIGHT_RESPONSE_PROPENSITY,
        fatigue=settings.SNIPER_WEIGHT_FATIGUE,
    )


def _provider_lookup(db: Session) -> dict[str, MarylandProvider]:
    return {str(row.provider_id): row for row in db.query(MarylandProvider).all()}


def _candidate_from_provider(provider: MarylandProvider) -> ClinicianCandidate:
    compliance = 1 if str(provider.license_status).upper() == "VERIFIED" else 0
    return ClinicianCandidate(
        clinician_id=str(provider.provider_id),
        compliance=compliance,
        min_rate=float(provider.min_hourly_rate or 0),
        response_propensity=float(provider.response_propensity or 0),
        fatigue=float(provider.fatigue_score or 0),
    )


def _dispatch_block_reason(db: Session, provider: MarylandProvider) -> str | None:
    if str(provider.dispatch_status or "ACTIVE").upper() == "SUSPENDED":
        return "dispatch suspended"
    if str(provider.license_status or "").upper() != "VERIFIED":
        return "license not verified"
    if has_active_exclusion(db, provider.provider_id):
        return "exclusion screening block"
    if has_expired_required_documents(db, provider.provider_id):
        return "expired compliance document"
    return None


def _geo_eligible_provider_ids(
    db: Session,
    facility: MarylandFacility | None,
    *,
    facility_state: str,
    radius_miles: float,
) -> set | None:
    if facility is None:
        return None
    facility_coords = _coords(facility)
    if not facility_coords or not postgis_geo_ready(db):
        return None
    return query_geo_eligible_provider_ids(
        db,
        facility_longitude=facility_coords[1],
        facility_latitude=facility_coords[0],
        state=facility_state,
        radius_miles=radius_miles,
    )


def _provider_within_geo_radius(
    provider: MarylandProvider,
    facility: MarylandFacility | None,
    *,
    radius_miles: float,
) -> bool:
    if facility is None:
        return True
    facility_coords = _coords(facility)
    provider_coords = _coords(provider)
    if not facility_coords or not provider_coords:
        return True
    distance = haversine_miles(
        facility_coords[0],
        facility_coords[1],
        provider_coords[0],
        provider_coords[1],
    )
    return distance <= radius_miles


def rank_offer_from_db(db: Session, offer_id: UUID) -> OfferRankResponse:
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        raise ValueError("offer_not_found")

    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == offer.facility_id)
        .first()
    )
    facility_name = facility.name if facility else "Unknown facility"
    facility_state = normalize_state(facility.state if facility else "MD")
    facility_type = facility.facility_type if facility else "HOSPITAL"
    geo_radius = float(settings.GEO_MATCH_RADIUS_MILES)
    geo_eligible_ids = _geo_eligible_provider_ids(
        db,
        facility,
        facility_state=facility_state,
        radius_miles=geo_radius,
    )

    pre_eliminated: list[EliminatedProviderOut] = []
    providers: list[MarylandProvider] = []
    for row in (
        db.query(MarylandProvider)
        .filter(MarylandProvider.state == facility_state)
        .all()
    ):
        if not clinician_qualifies_for_shift_role(
            row.credential_type,
            offer.shift_role,
            facility_state=facility_state,
        ):
            continue
        if not provider_supports_facility_type(row.service_lines, facility_type):
            continue
        if not credential_valid_in_state(row.credential_type, row.state):
            continue
        block_reason = _dispatch_block_reason(db, row)
        if block_reason:
            pre_eliminated.append(
                EliminatedProviderOut(
                    provider_id=row.provider_id,
                    full_name=row.full_name,
                    reason=block_reason,
                    rate_delta=float(row.min_hourly_rate or 0) - float(offer.hourly_pay_rate),
                )
            )
            continue
        if geo_eligible_ids is not None:
            if row.provider_id not in geo_eligible_ids:
                pre_eliminated.append(
                    EliminatedProviderOut(
                        provider_id=row.provider_id,
                        full_name=row.full_name,
                        reason="outside geo match radius",
                        rate_delta=float(row.min_hourly_rate or 0) - float(offer.hourly_pay_rate),
                    )
                )
                continue
        elif not _provider_within_geo_radius(row, facility, radius_miles=geo_radius):
            pre_eliminated.append(
                EliminatedProviderOut(
                    provider_id=row.provider_id,
                    full_name=row.full_name,
                    reason="outside geo match radius",
                    rate_delta=float(row.min_hourly_rate or 0) - float(offer.hourly_pay_rate),
                )
            )
            continue
        providers.append(row)
    candidates = [_candidate_from_provider(row) for row in providers]
    ranked, eliminated = rank_clinicians_for_shift(
        shift_pay=float(offer.hourly_pay_rate),
        candidates=candidates,
        weights=_weights(),
    )
    lookup = {str(row.provider_id): row for row in providers}

    ranked_out = []
    notify_order: list[UUID] = []
    for row in ranked:
        provider = lookup[row.clinician_id]
        notify_order.append(provider.provider_id)
        ranked_out.append(
            RankedProviderOut(
                provider_id=provider.provider_id,
                full_name=provider.full_name,
                phone_number=provider.phone_number,
                credential_type=provider.credential_type,
                rank=row.rank,
                priority_score=row.priority_score,
                rate_delta=row.rate_delta,
            )
        )

    eliminated_out = list(pre_eliminated)
    for row in eliminated:
        provider = lookup.get(row.clinician_id)
        eliminated_out.append(
            EliminatedProviderOut(
                provider_id=UUID(row.clinician_id),
                full_name=provider.full_name if provider else row.clinician_id,
                reason=row.reason,
                rate_delta=row.rate_delta,
            )
        )

    shift_starts_at, shift_ends_at = resolve_offer_shift_window(offer)
    return OfferRankResponse(
        offer_id=offer.offer_id,
        facility_name=facility_name,
        shift_role=offer.shift_role,
        hourly_pay_rate=float(offer.hourly_pay_rate),
        notify_order=notify_order,
        ranked=ranked_out,
        eliminated=eliminated_out,
        fill_probability_90s=round(placement_probability(1.5, p_max=settings.PLACEMENT_P_MAX, decay_lambda=settings.PLACEMENT_DECAY_LAMBDA), 4),
        facility_state=facility_state,
        shift_starts_at=shift_starts_at,
        shift_ends_at=shift_ends_at,
    )


def _notify_email_for_clinician(
    db: Session,
    *,
    offer_id: UUID,
    provider: MarylandProvider,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    reply_keyword: str,
    shift_starts_at: datetime | None = None,
    shift_ends_at: datetime | None = None,
    broadcast_wave_id: UUID | None,
    commit: bool,
) -> EmailDeliveryOut | None:
    if not settings.EMAIL_ALERTS_ENABLED:
        return None

    schedule_line = ""
    if shift_starts_at is not None and shift_ends_at is not None:
        schedule_line = f"\n  When: {format_shift_window_et(shift_starts_at, shift_ends_at)}"

    subject, body = build_shift_alert_email(
        facility_name=facility_name,
        shift_role=shift_role,
        hourly_pay_rate=hourly_pay_rate,
        reply_keyword=reply_keyword,
        clinician_name=provider.full_name,
        schedule_line=schedule_line,
    )
    email = send_shift_email(to_address=provider.email, subject=subject, message_body=body)
    if email.status == "SKIPPED":
        return None

    db.add(
        ShiftNotificationLog(
            offer_id=offer_id,
            provider_id=provider.provider_id,
            channel="EMAIL",
            status=email.status,
            message_body=body,
            broadcast_wave_id=broadcast_wave_id,
        )
    )
    refresh_provider_sniper_scores(db, provider.provider_id, commit=False)
    if commit:
        db.commit()
    return EmailDeliveryOut(
        provider_id=provider.provider_id,
        email_address=provider.email,
        status=email.status,
        mode=email.mode,
        subject=email.subject,
        message_body=email.message_body,
        message_id=email.message_id,
    )


def _notify_push_for_clinician(
    db: Session,
    *,
    offer_id: UUID,
    provider: MarylandProvider,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    reply_keyword: str = "YES",
    shift_starts_at: datetime | None = None,
    shift_ends_at: datetime | None = None,
    broadcast_wave_id: UUID | None,
    commit: bool,
) -> list[PushDeliveryOut]:
    if not settings.PUSH_ALERTS_ENABLED:
        return []

    schedule_line = ""
    if shift_starts_at is not None and shift_ends_at is not None:
        schedule_line = f" · {format_shift_window_et(shift_starts_at, shift_ends_at)}"

    title, body = build_shift_alert_push(
        facility_name=facility_name,
        shift_role=shift_role,
        hourly_pay_rate=hourly_pay_rate,
        reply_keyword=reply_keyword,
        schedule_line=schedule_line,
    )
    subscriptions = list_push_subscriptions_for_provider(db, provider.provider_id)
    if not subscriptions:
        return []

    deliveries: list[PushDeliveryOut] = []
    for subscription in subscriptions:
        push = send_shift_push(
            endpoint=subscription.endpoint,
            p256dh_key=subscription.p256dh_key,
            auth_key=subscription.auth_key,
            title=title,
            message_body=body,
            data={"offer_id": str(offer_id), "reply_keyword": reply_keyword},
        )
        if push.status == "SKIPPED":
            continue
        touch_push_subscription(db, subscription)
        db.add(
            ShiftNotificationLog(
                offer_id=offer_id,
                provider_id=provider.provider_id,
                channel="PUSH",
                status=push.status,
                message_body=body,
                broadcast_wave_id=broadcast_wave_id,
            )
        )
        deliveries.append(
            PushDeliveryOut(
                provider_id=provider.provider_id,
                subscription_id=subscription.subscription_id,
                endpoint=subscription.endpoint,
                status=push.status,
                mode=push.mode,
                title=push.title,
                message_body=push.message_body,
                receipt_id=push.receipt_id,
            )
        )

    if deliveries:
        refresh_provider_sniper_scores(db, provider.provider_id, commit=False)
    if commit:
        db.commit()
    return deliveries


def notify_single_ranked_clinician(
    db: Session,
    offer_id: UUID,
    ranked_row: RankedProviderOut,
    *,
    facility_name: str,
    shift_role: str,
    hourly_pay_rate: float,
    reply_keyword: str = "YES",
    shift_starts_at: datetime | None = None,
    shift_ends_at: datetime | None = None,
    broadcast_wave_id: UUID | None = None,
    commit: bool = True,
) -> SmsDeliveryOut:
    message_body = build_shift_alert_message(
        facility_name=facility_name,
        shift_role=shift_role,
        hourly_pay_rate=hourly_pay_rate,
        reply_keyword=reply_keyword,
        shift_starts_at=shift_starts_at,
        shift_ends_at=shift_ends_at,
    )
    sms = send_shift_sms(to_number=ranked_row.phone_number, message_body=message_body)
    db.add(
        ShiftNotificationLog(
            offer_id=offer_id,
            provider_id=ranked_row.provider_id,
            channel="SMS",
            status=sms.status,
            message_body=message_body,
            broadcast_wave_id=broadcast_wave_id,
        )
    )
    refresh_provider_sniper_scores(db, ranked_row.provider_id, commit=False)
    if commit:
        db.commit()
    return SmsDeliveryOut(
        provider_id=ranked_row.provider_id,
        phone_number=ranked_row.phone_number,
        status=sms.status,
        mode=sms.mode,
        message_body=message_body,
        twilio_sid=sms.twilio_sid,
    )


def notify_top_clinicians_for_offer(
    db: Session,
    offer_id: UUID,
    *,
    max_recipients: int = 1,
    reply_keyword: str = "YES",
) -> NotifyResponse:
    ranking = rank_offer_from_db(db, offer_id)
    if not ranking.ranked:
        return NotifyResponse(**ranking.model_dump(), deliveries=[], email_deliveries=[], push_deliveries=[])

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        raise ValueError("offer_not_found")

    provider_lookup = _provider_lookup(db)
    offer.compliance_lock_status = "BROADCASTING"
    wave_id = uuid4()
    offer.broadcast_wave_id = wave_id
    db.flush()
    shift_starts_at, shift_ends_at = resolve_offer_shift_window(offer)

    deliveries: list[SmsDeliveryOut] = []
    email_deliveries: list[EmailDeliveryOut] = []
    push_deliveries: list[PushDeliveryOut] = []
    for ranked_row in ranking.ranked[:max_recipients]:
        deliveries.append(
            notify_single_ranked_clinician(
                db,
                offer_id,
                ranked_row,
                facility_name=ranking.facility_name,
                shift_role=ranking.shift_role,
                hourly_pay_rate=ranking.hourly_pay_rate,
                reply_keyword=reply_keyword,
                shift_starts_at=shift_starts_at,
                shift_ends_at=shift_ends_at,
                broadcast_wave_id=wave_id,
                commit=False,
            )
        )
        provider = provider_lookup.get(str(ranked_row.provider_id))
        if provider is not None:
            email_delivery = _notify_email_for_clinician(
                db,
                offer_id=offer_id,
                provider=provider,
                facility_name=ranking.facility_name,
                shift_role=ranking.shift_role,
                hourly_pay_rate=ranking.hourly_pay_rate,
                reply_keyword=reply_keyword,
                shift_starts_at=shift_starts_at,
                shift_ends_at=shift_ends_at,
                broadcast_wave_id=wave_id,
                commit=False,
            )
            if email_delivery is not None:
                email_deliveries.append(email_delivery)
            push_deliveries.extend(
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
                    broadcast_wave_id=wave_id,
                    commit=False,
                )
            )

    for delivery in deliveries:
        log_ops_event(
            db,
            event_type="SHIFT_NOTIFY",
            actor="shift_sniper",
            entity_type="offer",
            entity_id=offer_id,
            summary=f"SMS sent to {delivery.phone_number}",
            metadata={"provider_id": str(delivery.provider_id), "status": delivery.status, "mode": delivery.mode, "channel": "SMS"},
            commit=False,
        )
    for delivery in email_deliveries:
        log_ops_event(
            db,
            event_type="SHIFT_NOTIFY",
            actor="shift_sniper",
            entity_type="offer",
            entity_id=offer_id,
            summary=f"Email sent to {delivery.email_address}",
            metadata={"provider_id": str(delivery.provider_id), "status": delivery.status, "mode": delivery.mode, "channel": "EMAIL"},
            commit=False,
        )
    for delivery in push_deliveries:
        log_ops_event(
            db,
            event_type="SHIFT_NOTIFY",
            actor="shift_sniper",
            entity_type="offer",
            entity_id=offer_id,
            summary=f"Push sent to subscription {delivery.subscription_id}",
            metadata={"provider_id": str(delivery.provider_id), "status": delivery.status, "mode": delivery.mode, "channel": "PUSH"},
            commit=False,
        )

    db.commit()
    return NotifyResponse(
        **ranking.model_dump(),
        deliveries=deliveries,
        email_deliveries=email_deliveries,
        push_deliveries=push_deliveries,
    )
