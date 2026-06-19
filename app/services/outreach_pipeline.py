"""B2B outreach campaign orchestration for crisis-flagged Maryland nursing homes."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    FacilityCrisisSignal,
    FacilityOutreachContact,
    JobBoardCrisisListing,
    MarylandFacility,
    OutreachEmailLog,
)
from app.services.contact_enrichment import enrich_facility_contacts
from app.services.email_alerts import send_shift_email
from app.services.ops_metrics import log_ops_event
from app.services.outreach_llm import generate_crisis_outreach_email


def _latest_crisis_summary(db: Session, facility_id) -> str:
    signal = (
        db.query(FacilityCrisisSignal)
        .filter(FacilityCrisisSignal.facility_id == facility_id)
        .order_by(FacilityCrisisSignal.detected_at.desc())
        .first()
    )
    if signal is not None:
        return signal.summary
    listing = (
        db.query(JobBoardCrisisListing)
        .filter(
            JobBoardCrisisListing.facility_id == facility_id,
            JobBoardCrisisListing.is_crisis == "true",
        )
        .order_by(JobBoardCrisisListing.days_open.desc())
        .first()
    )
    if listing is not None:
        return (
            f"Your facility has had a {listing.shift_role} role posted on {listing.source} "
            f"for {int(listing.days_open)} days."
        )
    return "Continuous CNA/LPN recruiting suggests ongoing floor staffing pressure."


def list_outreach_targets(db: Session, *, limit: int = 25) -> list[dict]:
    crisis_facility_ids = {
        row[0]
        for row in db.query(FacilityCrisisSignal.facility_id)
        .filter(FacilityCrisisSignal.severity.in_(("MEDIUM", "HIGH")))
        .distinct()
        .all()
        if row[0] is not None
    }
    job_board_ids = {
        row[0]
        for row in db.query(JobBoardCrisisListing.facility_id)
        .filter(JobBoardCrisisListing.is_crisis == "true", JobBoardCrisisListing.facility_id.isnot(None))
        .distinct()
        .all()
        if row[0] is not None
    }
    facility_ids = list(crisis_facility_ids | job_board_ids)[:limit]
    if not facility_ids:
        return []

    facilities = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id.in_(facility_ids))
        .order_by(MarylandFacility.name.asc())
        .all()
    )
    targets: list[dict] = []
    for facility in facilities:
        contact_count = (
            db.query(func.count(FacilityOutreachContact.contact_id))
            .filter(FacilityOutreachContact.facility_id == facility.facility_id)
            .scalar()
            or 0
        )
        targets.append(
            {
                "facility_id": str(facility.facility_id),
                "facility_name": facility.name,
                "county": facility.county,
                "city": facility.city,
                "state": facility.state,
                "crisis_summary": _latest_crisis_summary(db, facility.facility_id),
                "contact_count": int(contact_count),
            }
        )
    return targets


def enrich_contacts_for_facility(db: Session, facility_id) -> dict:
    facility = db.query(MarylandFacility).filter(MarylandFacility.facility_id == facility_id).first()
    if facility is None:
        raise ValueError("facility_not_found")

    enriched = enrich_facility_contacts(
        facility_name=facility.name,
        city=facility.city,
        state=facility.state,
    )
    created = 0
    for row in enriched:
        existing = (
            db.query(FacilityOutreachContact)
            .filter(
                FacilityOutreachContact.facility_id == facility.facility_id,
                FacilityOutreachContact.email == row.email,
            )
            .first()
        )
        if existing is not None:
            existing.full_name = row.full_name
            existing.title = row.title
            existing.source = row.source
            continue
        db.add(
            FacilityOutreachContact(
                facility_id=facility.facility_id,
                full_name=row.full_name,
                title=row.title,
                email=row.email,
                source=row.source,
            )
        )
        created += 1
    db.commit()
    return {
        "facility_id": str(facility.facility_id),
        "facility_name": facility.name,
        "contacts_enriched": len(enriched),
        "contacts_created": created,
    }


def run_outreach_campaign(db: Session, *, limit: int = 10, send: bool = False) -> dict:
    targets = list_outreach_targets(db, limit=limit)
    emails_drafted = 0
    emails_sent = 0
    contacts_enriched = 0

    for target in targets:
        enrich_result = enrich_contacts_for_facility(db, target["facility_id"])
        contacts_enriched += enrich_result["contacts_enriched"]
        contacts = (
            db.query(FacilityOutreachContact)
            .filter(FacilityOutreachContact.facility_id == target["facility_id"])
            .order_by(FacilityOutreachContact.title.asc())
            .all()
        )
        facility = db.query(MarylandFacility).filter(MarylandFacility.facility_id == target["facility_id"]).one()
        crisis_summary = target["crisis_summary"]
        for contact in contacts[:2]:
            draft = generate_crisis_outreach_email(
                administrator_name=contact.full_name,
                facility_name=facility.name,
                city=facility.city,
                county=facility.county,
                crisis_summary=crisis_summary,
            )
            emails_drafted += 1
            delivery_status = "DRAFT"
            delivery_mode = draft.mode
            if send and settings.OUTREACH_EMAIL_ENABLED:
                if settings.OUTREACH_EMAIL_DRY_RUN or settings.EMAIL_DRY_RUN:
                    result = send_shift_email(
                        to_address=contact.email,
                        subject=draft.subject,
                        message_body=draft.body,
                    )
                    delivery_status = result.status
                    delivery_mode = result.mode
                    if result.status in {"SENT", "DRY_RUN"}:
                        emails_sent += 1
                else:
                    result = send_shift_email(
                        to_address=contact.email,
                        subject=draft.subject,
                        message_body=draft.body,
                    )
                    delivery_status = result.status
                    delivery_mode = result.mode
                    if result.status == "SENT":
                        emails_sent += 1
            db.add(
                OutreachEmailLog(
                    facility_id=facility.facility_id,
                    contact_id=contact.contact_id,
                    recipient_name=contact.full_name,
                    recipient_email=contact.email,
                    subject=draft.subject,
                    body=draft.body,
                    status=delivery_status if send else "DRAFT",
                    mode=delivery_mode,
                    crisis_context=crisis_summary[:500],
                )
            )
            log_ops_event(
                db,
                event_type="OUTREACH_EMAIL",
                actor="outreach_pipeline",
                entity_type="facility",
                entity_id=facility.facility_id,
                summary=f"Outreach email {delivery_status} to {contact.email}",
                metadata={"contact_id": str(contact.contact_id), "mode": delivery_mode},
                commit=False,
            )

    db.commit()
    return {
        "targets": len(targets),
        "contacts_enriched": contacts_enriched,
        "emails_drafted": emails_drafted,
        "emails_sent": emails_sent,
        "send_enabled": send,
    }


def list_outreach_email_log(db: Session, *, limit: int = 50) -> list[dict]:
    rows = (
        db.query(OutreachEmailLog, MarylandFacility)
        .join(MarylandFacility, MarylandFacility.facility_id == OutreachEmailLog.facility_id)
        .order_by(OutreachEmailLog.sent_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "email_id": str(log.email_id),
            "facility_id": str(facility.facility_id),
            "facility_name": facility.name,
            "recipient_name": log.recipient_name,
            "recipient_email": log.recipient_email,
            "subject": log.subject,
            "status": log.status,
            "mode": log.mode,
            "crisis_context": log.crisis_context,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        }
        for log, facility in rows
    ]
