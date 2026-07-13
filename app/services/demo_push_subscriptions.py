"""Register dry-run Web Push subscriptions for @offercare.demo clinicians."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ClinicianPushSubscription, MarylandProvider
from app.services.push_subscriptions import register_push_subscription

DEMO_PUSH_P256DH_KEY = "demo-p256dh-key"
DEMO_PUSH_AUTH_KEY = "demo-auth-key"
DEMO_PUSH_USER_AGENT = "VettedMe demo push subscription"


def demo_push_endpoint(provider_id: UUID) -> str:
    return f"https://push.offercare.demo/providers/{provider_id}"


def ensure_demo_push_subscriptions(db: Session) -> dict:
    providers = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.like("%@offercare.demo"))
        .order_by(MarylandProvider.email.asc())
        .all()
    )
    created = 0
    existing = 0
    for provider in providers:
        endpoint = demo_push_endpoint(provider.provider_id)
        row = (
            db.query(ClinicianPushSubscription)
            .filter(ClinicianPushSubscription.endpoint == endpoint)
            .first()
        )
        if row is None:
            created += 1
        else:
            existing += 1
        register_push_subscription(
            db,
            provider.provider_id,
            endpoint=endpoint,
            p256dh_key=DEMO_PUSH_P256DH_KEY,
            auth_key=DEMO_PUSH_AUTH_KEY,
            user_agent=DEMO_PUSH_USER_AGENT,
        )

    return {
        "clinician_count": len(providers),
        "created": created,
        "existing": existing,
    }
