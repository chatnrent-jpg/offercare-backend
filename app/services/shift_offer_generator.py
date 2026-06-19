"""Auto-create open shift offers for Maryland facilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility, OfferCareJobOffer
from app.services.care_taxonomy import (
    facility_type_label,
    shift_role_label,
    shift_templates_for_facility_type,
)
from app.services.shift_schedule import apply_default_shift_schedule, resolve_offer_shift_window


@dataclass(frozen=True)
class ShiftAutoCreateResult:
    facility_id: UUID
    facility_name: str
    created_offers: list[UUID]
    skipped_roles: list[str]


def _facility_has_open_offer(db: Session, facility_id: UUID, shift_role: str) -> bool:
    return (
        db.query(OfferCareJobOffer.offer_id)
        .filter(
            OfferCareJobOffer.facility_id == facility_id,
            OfferCareJobOffer.shift_role == shift_role,
            OfferCareJobOffer.compliance_lock_status == "BROADCASTING",
        )
        .first()
        is not None
    )


def _serialize_open_shift(offer: OfferCareJobOffer, facility: MarylandFacility) -> dict:
    shift_starts_at, shift_ends_at = resolve_offer_shift_window(offer)
    return {
        "offer_id": offer.offer_id,
        "facility_id": facility.facility_id,
        "facility_name": facility.name,
        "facility_type": facility.facility_type,
        "facility_type_label": facility_type_label(facility.facility_type),
        "county": facility.county,
        "state": facility.state,
        "shift_role": offer.shift_role,
        "shift_role_label": shift_role_label(offer.shift_role),
        "hourly_pay_rate": float(offer.hourly_pay_rate),
        "compliance_lock_status": offer.compliance_lock_status,
        "shift_starts_at": shift_starts_at,
        "shift_ends_at": shift_ends_at,
        "created_at": offer.created_at,
    }


def auto_create_shifts_for_facilities(
    db: Session,
    facility_ids: list[UUID],
    *,
    notify_matched_push: bool | None = None,
) -> tuple[int, int, int]:
    if not facility_ids:
        return 0, 0, 0
    facilities = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id.in_(facility_ids))
        .order_by(MarylandFacility.name.asc())
        .all()
    )
    offers_created = 0
    created_offer_ids: list[UUID] = []
    for facility in facilities:
        result = auto_create_shifts_for_facility(db, facility)
        offers_created += len(result.created_offers)
        created_offer_ids.extend(result.created_offers)

    matched_push_sent = 0
    should_notify = (
        settings.MATCHED_SHIFT_PUSH_ON_AUTO_CREATE
        if notify_matched_push is None
        else notify_matched_push
    )
    if should_notify and created_offer_ids:
        from app.services.matched_shift_alerts import notify_matched_clinicians_for_offers

        matched_push_sent = notify_matched_clinicians_for_offers(db, created_offer_ids)

    return len(facilities), offers_created, matched_push_sent


def auto_create_shifts_for_facility(
    db: Session,
    facility: MarylandFacility,
    *,
    templates: tuple[tuple[str, float], ...] | None = None,
) -> ShiftAutoCreateResult:
    roles = templates or shift_templates_for_facility_type(facility.facility_type)
    created: list[UUID] = []
    skipped: list[str] = []

    for shift_role, hourly_pay_rate in roles:
        if _facility_has_open_offer(db, facility.facility_id, shift_role):
            skipped.append(shift_role)
            continue
        offer = OfferCareJobOffer(
            facility_id=facility.facility_id,
            shift_role=shift_role,
            hourly_pay_rate=hourly_pay_rate,
            compliance_lock_status="BROADCASTING",
        )
        apply_default_shift_schedule(offer)
        db.add(offer)
        db.flush()
        created.append(offer.offer_id)

    if created:
        db.commit()

    return ShiftAutoCreateResult(
        facility_id=facility.facility_id,
        facility_name=facility.name,
        created_offers=created,
        skipped_roles=skipped,
    )


def auto_create_open_shifts(
    db: Session,
    *,
    limit: int = 25,
    state: str | None = None,
    county: str | None = None,
    icu_rate: float = 120.0,
    er_rate: float = 110.0,
    med_surg_rate: float = 95.0,
) -> list[ShiftAutoCreateResult]:
    hospital_templates = (
        ("ICU_RN", icu_rate),
        ("ER_RN", er_rate),
        ("MED_SURG_RN", med_surg_rate),
    )
    query = db.query(MarylandFacility).order_by(MarylandFacility.name.asc())
    if state:
        query = query.filter(MarylandFacility.state == state.strip().upper())
    if county:
        query = query.filter(MarylandFacility.county.ilike(f"%{county.strip()}%"))
    facilities = query.limit(limit).all()

    results: list[ShiftAutoCreateResult] = []
    for facility in facilities:
        templates = (
            hospital_templates
            if facility.facility_type == "HOSPITAL"
            else shift_templates_for_facility_type(facility.facility_type)
        )
        results.append(auto_create_shifts_for_facility(db, facility, templates=templates))
    return results


def list_open_shifts(
    db: Session,
    *,
    limit: int = 50,
    state: str | None = None,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
) -> list[dict]:
    query = (
        db.query(OfferCareJobOffer, MarylandFacility)
        .join(MarylandFacility, OfferCareJobOffer.facility_id == MarylandFacility.facility_id)
        .filter(OfferCareJobOffer.compliance_lock_status == "BROADCASTING")
        .order_by(OfferCareJobOffer.created_at.desc())
    )
    if state:
        query = query.filter(MarylandFacility.state == state.strip().upper())
    if county:
        query = query.filter(MarylandFacility.county.ilike(f"%{county.strip()}%"))
    if facility_type:
        query = query.filter(MarylandFacility.facility_type.ilike(facility_type.strip()))
    if shift_role:
        query = query.filter(OfferCareJobOffer.shift_role.ilike(shift_role.strip()))
    if min_pay is not None:
        query = query.filter(OfferCareJobOffer.hourly_pay_rate >= min_pay)
    if starts_after is not None:
        query = query.filter(OfferCareJobOffer.shift_starts_at >= starts_after)
    rows = query.limit(limit).all()
    return [_serialize_open_shift(offer, facility) for offer, facility in rows]


def get_open_shift_filters(db: Session) -> dict[str, list[str]]:
    rows = (
        db.query(
            MarylandFacility.state,
            MarylandFacility.county,
            MarylandFacility.facility_type,
            OfferCareJobOffer.shift_role,
        )
        .join(MarylandFacility, OfferCareJobOffer.facility_id == MarylandFacility.facility_id)
        .filter(OfferCareJobOffer.compliance_lock_status == "BROADCASTING")
        .distinct()
        .all()
    )
    states = sorted({str(state) for state, _, _, _ in rows if state})
    counties = sorted({str(county) for _, county, _, _ in rows if county})
    facility_types = sorted({str(facility_type) for _, _, facility_type, _ in rows if facility_type})
    roles = sorted({str(role) for _, _, _, role in rows if role})
    return {
        "states": states,
        "counties": counties,
        "facility_types": facility_types,
        "shift_roles": roles,
    }


def get_open_shift_by_id(db: Session, offer_id: UUID) -> dict | None:
    row = (
        db.query(OfferCareJobOffer, MarylandFacility)
        .join(MarylandFacility, OfferCareJobOffer.facility_id == MarylandFacility.facility_id)
        .filter(OfferCareJobOffer.offer_id == offer_id)
        .first()
    )
    if row is None:
        return None
    offer, facility = row
    return _serialize_open_shift(offer, facility)
