"""Admin updates to explicit offer shift schedules."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MarylandFacility, OfferCareJobOffer
from app.services.ops_metrics import log_ops_event
from app.services.shift_offer_generator import get_open_shift_by_id
from app.services.shift_schedule import format_shift_window_et, set_offer_shift_schedule


def update_offer_shift_schedule(
    db: Session,
    offer_id: UUID,
    *,
    shift_starts_at,
    shift_ends_at,
    actor: str = "admin",
) -> dict:
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        raise ValueError("offer_not_found")
    if str(offer.compliance_lock_status or "").upper() == "LOCKED":
        raise ValueError("offer_locked")

    start, end = set_offer_shift_schedule(
        offer,
        shift_starts_at=shift_starts_at,
        shift_ends_at=shift_ends_at,
    )
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == offer.facility_id)
        .first()
    )
    facility_name = facility.name if facility else "Unknown facility"
    log_ops_event(
        db,
        event_type="SHIFT_SCHEDULE",
        actor=actor,
        entity_type="offer",
        entity_id=offer_id,
        summary=f"Updated schedule for {facility_name} {offer.shift_role} → {format_shift_window_et(start, end)}",
        metadata={
            "shift_starts_at": start.isoformat(),
            "shift_ends_at": end.isoformat(),
        },
        commit=False,
    )
    db.commit()
    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        raise ValueError("offer_not_found")
    return row
