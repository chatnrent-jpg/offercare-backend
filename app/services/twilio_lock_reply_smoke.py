"""Twilio YES-reply lock smoke test — end-to-end without a real handset (step 135)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility, OfferCareJobOffer
from app.seed import seed_saint_judes_demo
from app.services.integrations import twilio_inbound_webhook_url
from app.services.shift_lock import lock_shift_from_sms_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer


def run_twilio_lock_reply_smoke(db: Session, *, phone_number: str | None = None) -> dict:
    seeded = seed_saint_judes_demo(db)
    offer_id = UUID(seeded["offer_id"])
    notify_top_clinicians_for_offer(db, offer_id, max_recipients=1)

    phone = str(phone_number or "+14105550001").strip()
    keyword = str(settings.TWILIO_REPLY_KEYWORD or "YES").strip().upper()
    result = lock_shift_from_sms_reply(
        db,
        from_phone=phone,
        message_body=keyword,
        reply_keyword=keyword,
    )

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    facility_name = "Saint Jude's ICU"
    if offer and offer.facility_id:
        facility = db.query(MarylandFacility).filter(MarylandFacility.facility_id == offer.facility_id).first()
        if facility:
            facility_name = facility.name
    return {
        "ok": result.status == "locked",
        "status": result.status,
        "message": result.message,
        "offer_id": str(result.offer_id) if result.offer_id else str(offer_id),
        "provider_id": str(result.provider_id) if result.provider_id else None,
        "placement_id": str(result.placement_id) if result.placement_id else None,
        "phone_number": phone,
        "reply_keyword": keyword,
        "facility_name": facility_name,
        "compliance_lock_status": offer.compliance_lock_status if offer else None,
        "inbound_webhook_url": twilio_inbound_webhook_url(),
    }
