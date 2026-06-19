"""Clinician Web Push subscription storage."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ClinicianPushSubscription


def list_push_subscriptions_for_provider(db: Session, provider_id: UUID) -> list[ClinicianPushSubscription]:
    return (
        db.query(ClinicianPushSubscription)
        .filter(ClinicianPushSubscription.provider_id == provider_id)
        .order_by(ClinicianPushSubscription.created_at.asc())
        .all()
    )


def register_push_subscription(
    db: Session,
    provider_id: UUID,
    *,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    user_agent: str | None = None,
) -> ClinicianPushSubscription:
    endpoint = endpoint.strip()
    if not endpoint:
        raise ValueError("invalid_endpoint")

    existing = (
        db.query(ClinicianPushSubscription)
        .filter(ClinicianPushSubscription.endpoint == endpoint)
        .first()
    )
    if existing is not None:
        if existing.provider_id != provider_id:
            raise ValueError("endpoint_owned_by_other_provider")
        existing.p256dh_key = p256dh_key
        existing.auth_key = auth_key
        existing.user_agent = user_agent
        db.commit()
        db.refresh(existing)
        return existing

    row = ClinicianPushSubscription(
        provider_id=provider_id,
        endpoint=endpoint,
        p256dh_key=p256dh_key,
        auth_key=auth_key,
        user_agent=user_agent,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def unregister_push_subscription(db: Session, provider_id: UUID, *, endpoint: str) -> bool:
    row = (
        db.query(ClinicianPushSubscription)
        .filter(
            ClinicianPushSubscription.provider_id == provider_id,
            ClinicianPushSubscription.endpoint == endpoint.strip(),
        )
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def touch_push_subscription(db: Session, subscription: ClinicianPushSubscription) -> None:
    subscription.last_used_at = datetime.now(timezone.utc)
    db.add(subscription)
