"""Ensure the walkthrough demo CNA has at least one lockable open shift."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ClinicalPlacementLedger, MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.services.clinician_schedule import provider_calendar_token
from app.services.demo_portal_accounts import SAMPLE_DEMO_PORTAL_EMAIL, ensure_demo_seed_clinician
from app.services.shift_matching import count_portal_lockable_shifts, is_demo_walkthrough_provider
from app.services.shift_schedule import apply_default_shift_schedule, validate_shift_window


def _resolve_offer_for_orphan_commitment(
    db: Session,
    *,
    event: Any,
    meta: dict,
    shift_role: str,
) -> OfferCareJobOffer | None:
    offer_id_str = str(event.shift_id or meta.get("offer_id") or "").strip()
    offer: OfferCareJobOffer | None = None
    if offer_id_str:
        try:
            offer = (
                db.query(OfferCareJobOffer)
                .filter(OfferCareJobOffer.offer_id == UUID(offer_id_str))
                .first()
            )
        except ValueError:
            offer = None

    if offer is not None:
        return offer

    facility_id_str = str(meta.get("facility_id") or "").strip()
    if facility_id_str:
        try:
            offer = (
                db.query(OfferCareJobOffer)
                .filter(
                    OfferCareJobOffer.facility_id == UUID(facility_id_str),
                    OfferCareJobOffer.shift_role == shift_role,
                )
                .order_by(OfferCareJobOffer.created_at.desc())
                .first()
            )
        except ValueError:
            offer = None

    if offer is None:
        facility_name = str(meta.get("facility_name") or "").strip()
        if facility_name:
            facility = (
                db.query(MarylandFacility)
                .filter(MarylandFacility.name == facility_name)
                .first()
            )
            if facility is not None:
                offer = (
                    db.query(OfferCareJobOffer)
                    .filter(
                        OfferCareJobOffer.facility_id == facility.facility_id,
                        OfferCareJobOffer.shift_role == shift_role,
                    )
                    .order_by(OfferCareJobOffer.created_at.desc())
                    .first()
                )

    if offer is None:
        return None

    event.shift_id = str(offer.offer_id)
    if event.start_time and event.end_time:
        try:
            start, end = validate_shift_window(
                shift_starts_at=event.start_time,
                shift_ends_at=event.end_time,
            )
            offer.shift_starts_at = start
            offer.shift_ends_at = end
        except ValueError:
            pass
    return offer


def repair_demo_portal_placements(db: Session, provider: MarylandProvider) -> int:
    """Backfill placement ledger rows from calendar SHIFT_COMMITMENT events (demo re-seed drift)."""
    if not is_demo_walkthrough_provider(provider):
        return 0

    try:
        from app.models import ClinicianCalendarEvent
    except Exception:
        return 0

    token = provider_calendar_token(provider)
    if not token:
        return 0

    events = (
        db.query(ClinicianCalendarEvent)
        .filter(
            ClinicianCalendarEvent.provider_id == token,
            ClinicianCalendarEvent.event_type == "SHIFT_COMMITMENT",
        )
        .all()
    )
    repaired = 0
    for event in events:
        try:
            meta = json.loads(event.metadata_json or "{}")
        except json.JSONDecodeError:
            meta = {}
        shift_role = str(meta.get("shift_role") or "CNA")
        offer = _resolve_offer_for_orphan_commitment(db, event=event, meta=meta, shift_role=shift_role)
        if offer is None:
            continue

        existing = (
            db.query(ClinicalPlacementLedger)
            .filter(
                ClinicalPlacementLedger.offer_id == offer.offer_id,
                ClinicalPlacementLedger.assigned_clinician_id == provider.provider_id,
            )
            .first()
        )
        if existing is not None:
            continue

        facility_name = str(meta.get("facility_name") or "Maryland facility")
        hourly = float(getattr(offer, "hourly_pay_rate", None) or 24.0)
        db.add(
            ClinicalPlacementLedger(
                offer_id=offer.offer_id,
                facility_name=facility_name,
                clinical_unit=shift_role,
                hourly_bill_rate=hourly,
                assigned_clinician_id=provider.provider_id,
                compliance_snapshot_token="demo-calendar-repair",
                vms_submission_status="PENDING",
                outbound_payload_timestamp=event.start_time,
            )
        )
        offer.compliance_lock_status = "LOCKED"
        offer.assigned_provider_id = provider.provider_id
        meta["offer_id"] = str(offer.offer_id)
        meta["placement_repaired_at"] = datetime.now(timezone.utc).isoformat()
        event.metadata_json = json.dumps(meta, default=str)
        repaired += 1

    if repaired:
        db.commit()
    return repaired


def _spawn_demo_followup_offer(db: Session, *, facility_id: UUID) -> OfferCareJobOffer | None:
    """Add a fresh broadcasting CNA offer on a future day (avoids schedule conflict with prior locks)."""
    anchor = datetime.now(timezone.utc) + timedelta(days=3)
    while anchor.weekday() >= 5:
        anchor += timedelta(days=1)

    offer = OfferCareJobOffer(
        facility_id=facility_id,
        shift_role="CNA",
        hourly_pay_rate=24.0,
        compliance_lock_status="BROADCASTING",
    )
    db.add(offer)
    db.flush()
    apply_default_shift_schedule(offer, anchor=anchor)
    db.flush()
    return offer


def ensure_demo_replenish_after_payout(db: Session, provider: MarylandProvider) -> int:
    """After instant pay completes, spawn a fresh lockable shift for the walkthrough loop."""
    if not is_demo_walkthrough_provider(provider):
        return 0

    from app.services.clinician_payments import list_clinician_payments

    payments = list_clinician_payments(db, provider.provider_id)
    if not any(str(row.get("payout_status") or "").upper() == "PAID" for row in payments):
        return 0

    lockable = count_portal_lockable_shifts(db, provider, limit=50)
    if lockable > 0:
        return 0

    placements = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.assigned_clinician_id == provider.provider_id)
        .order_by(ClinicalPlacementLedger.outbound_payload_timestamp.desc())
        .all()
    )
    if not placements:
        return 0

    offer = (
        db.query(OfferCareJobOffer)
        .filter(OfferCareJobOffer.offer_id == placements[0].offer_id)
        .first()
    )
    facility_id = offer.facility_id if offer is not None else None
    if facility_id is None:
        from app.seed import seed_nj_nursing_home_demo

        seed_result = seed_nj_nursing_home_demo(db)
        raw = seed_result.get("facility_id")
        if raw is None:
            return 0
        facility_id = UUID(str(raw))

    spawned = _spawn_demo_followup_offer(db, facility_id=facility_id)
    if spawned is None:
        return 0
    db.commit()
    return 1


def ensure_demo_portal_lockable_shift(db: Session, *, email: str = SAMPLE_DEMO_PORTAL_EMAIL) -> dict:
    """Seed/repair NJ SNF demo offer so the sample CNA can lock a shift in the portal."""
    normalized = str(email or "").strip().lower()
    if not normalized.endswith("@offercare.demo"):
        return {"lockable_count": 0, "repaired": False}

    ensure_demo_seed_clinician(db, normalized)
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.email.ilike(normalized))
        .first()
    )
    if provider is None:
        return {"lockable_count": 0, "repaired": False}

    repair_demo_portal_placements(db, provider)

    lockable = count_portal_lockable_shifts(db, provider, limit=50)
    if lockable > 0:
        return {"lockable_count": lockable, "repaired": False, "sample_email": normalized}

    from app.seed import seed_nj_nursing_home_demo

    seed_result = seed_nj_nursing_home_demo(db)
    lockable = count_portal_lockable_shifts(db, provider, limit=50)
    if lockable > 0:
        return {
            "lockable_count": lockable,
            "repaired": True,
            "sample_email": normalized,
        }

    facility_id = seed_result.get("facility_id")
    if facility_id:
        _spawn_demo_followup_offer(db, facility_id=UUID(str(facility_id)))
        db.commit()
        lockable = count_portal_lockable_shifts(db, provider, limit=50)

    return {
        "lockable_count": lockable,
        "repaired": True,
        "sample_email": normalized,
        "spawned_followup": lockable > 0,
    }
