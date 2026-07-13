"""Maryland B2B outreach payload builder — Cursor generates · Manus executes campaigns."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.config import settings
from app.models import B2BRawLead, MdFacilityContact, MdMarketFacility, MdOutreachPayload

FACILITY_TYPE_LABELS = {
    "SNF": "skilled nursing",
    "ALF": "assisted living",
    "HHA": "home health",
}

CONTACT_ROLE_LABELS = {
    "ADMINISTRATOR": "Facility Administrator",
    "DON": "Director of Nursing",
    "HR_HEAD": "HR Director",
}


class OutreachLeadLike(Protocol):
    facility_type: str | None
    facility_county: str | None
    county: str | None
    facility_name: str | None
    decision_maker_name: str | None
    contact_name: str | None
    decision_maker_title: str | None
    contact_role: str | None


def _salutation(name: str | None, title: str | None) -> str:
    if name:
        return name.split()[0]
    if title and "DON" in title.upper():
        return "Director"
    return "there"


def build_outreach_copy(lead: OutreachLeadLike) -> dict[str, str]:
    """Personalized email/SMS scripts highlighting lookahead MBON compliance vetting."""
    facility_type = str(lead.facility_type or "SNF").upper()
    segment = FACILITY_TYPE_LABELS.get(facility_type, "long-term care")
    county = str(lead.facility_county or lead.county or "Maryland")
    name = str(lead.decision_maker_name or lead.contact_name or "").strip()
    title = str(lead.decision_maker_title or lead.contact_role or "Administrator").strip()
    facility = str(lead.facility_name or "your facility").strip()
    agency = settings.OUTREACH_AGENCY_NAME or "VettedMe.ai"
    sender = settings.OUTREACH_SENDER_NAME or "VettedMe Team"
    first = _salutation(name, title)

    email_subject = (
        f"{facility} — pre-vetted CNA/LPN/GNA coverage with automated MBON compliance"
    )
    email_body = (
        f"Hi {first},\n\n"
        f"I'm {sender} at {agency}. We support {segment} operators across {county} with "
        f"on-demand CNA, GNA, and LPN coverage — every clinician is run through automated "
        f"Maryland Board of Nursing (MBON) verification and GNA endorsement checks before "
        f"they appear in your lookahead shift queue.\n\n"
        f"What that means for {facility}:\n"
        f"• No surprise credential gaps on the floor\n"
        f"• Lookahead matching surfaces only compliance-cleared staff\n"
        f"• Regional home-health routing optimized by county ({county})\n\n"
        f"If staffing pressure is building, I can share a same-week coverage plan tailored "
        f"to your {facility_type} census. Reply here or call our staffing desk — happy to "
        f"walk your DON team through the vetting workflow.\n\n"
        f"— {sender}\n{agency}\n"
        f"Automated MBON/OHCQ compliance · Maryland LTC focus"
    )
    sms_body = (
        f"{agency}: Hi {first} — we place MBON-verified CNA/LPN/GNA staff in {county} "
        f"{segment} facilities with lookahead compliance vetting. Reply YES for a "
        f"coverage snapshot for {facility}."
    )[:320]

    return {
        "email_subject": email_subject,
        "email_body": email_body,
        "sms_body": sms_body,
    }


def _facility_contact_adapter(
    facility: MdMarketFacility,
    contact: MdFacilityContact,
) -> OutreachLeadLike:
    role = str(contact.contact_role or "ADMINISTRATOR").upper()
    title = CONTACT_ROLE_LABELS.get(role, role.replace("_", " ").title())

    class _Adapter:
        facility_type = facility.facility_type
        facility_county = facility.md_county
        county = facility.md_county
        facility_name = facility.company_name
        decision_maker_name = contact.full_name
        contact_name = contact.full_name
        decision_maker_title = title
        contact_role = role

    return _Adapter()  # type: ignore[return-value]


def build_outreach_copy_from_facility(
    facility: MdMarketFacility,
    contact: MdFacilityContact,
) -> dict[str, str]:
    return build_outreach_copy(_facility_contact_adapter(facility, contact))


def build_and_persist_outreach_payload(db: Session, lead: B2BRawLead) -> MdOutreachPayload:
    copy = build_outreach_copy(lead)
    payload = MdOutreachPayload(
        payload_id=uuid.uuid4(),
        lead_id=lead.lead_id,
        facility_name=lead.facility_name,
        decision_maker_name=lead.decision_maker_name,
        decision_maker_title=lead.decision_maker_title,
        direct_email=lead.direct_email,
        facility_county=lead.facility_county,
        facility_type=lead.facility_type,
        email_subject=copy["email_subject"],
        email_body=copy["email_body"],
        sms_body=copy["sms_body"],
        channel="EMAIL",
        status="READY",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(payload)
    lead.outreach_payload_json = json.dumps(
        {
            "payload_id": str(payload.payload_id),
            "email_subject": copy["email_subject"],
            "email_body": copy["email_body"],
            "sms_body": copy["sms_body"],
            "direct_email": lead.direct_email,
            "manus_action": "send_b2b_outreach",
        }
    )
    db.flush()
    return payload


def build_and_persist_outreach_from_contact(
    db: Session,
    facility: MdMarketFacility,
    contact: MdFacilityContact,
) -> MdOutreachPayload:
    copy = build_outreach_copy_from_facility(facility, contact)
    role = str(contact.contact_role or "ADMINISTRATOR").upper()
    title = CONTACT_ROLE_LABELS.get(role, role)
    payload = MdOutreachPayload(
        payload_id=uuid.uuid4(),
        facility_contact_id=contact.contact_id,
        facility_name=facility.company_name,
        decision_maker_name=contact.full_name,
        decision_maker_title=title,
        direct_email=contact.email,
        facility_county=facility.md_county,
        facility_type=facility.facility_type,
        email_subject=copy["email_subject"],
        email_body=copy["email_body"],
        sms_body=copy["sms_body"],
        channel="EMAIL",
        status="READY",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(payload)
    contact.notes = json.dumps(
        {
            "payload_id": str(payload.payload_id),
            "email_subject": copy["email_subject"],
            "manus_action": "send_b2b_outreach",
            "source": "facility_contacts",
        }
    )
    db.flush()
    return payload


def sync_ready_facility_contacts_to_outreach(db: Session, *, limit: int = 100) -> dict[str, Any]:
    """Build md_outreach_payloads for READY facility_contacts (idempotent)."""
    rows = (
        db.query(MdFacilityContact, MdMarketFacility)
        .join(MdMarketFacility, MdFacilityContact.facility_id == MdMarketFacility.facility_id)
        .filter(MdFacilityContact.outreach_status == "READY")
        .filter(MdFacilityContact.email.isnot(None))
        .order_by(MdMarketFacility.company_name.asc())
        .limit(limit)
        .all()
    )

    generated = 0
    skipped = 0
    payload_ids: list[str] = []

    for contact, facility in rows:
        existing = (
            db.query(MdOutreachPayload)
            .filter(
                MdOutreachPayload.facility_contact_id == contact.contact_id,
                MdOutreachPayload.status.in_(["READY", "CONTACTED"]),
            )
            .first()
        )
        if existing is None and contact.email:
            existing = (
                db.query(MdOutreachPayload)
                .filter(
                    MdOutreachPayload.direct_email == contact.email,
                    MdOutreachPayload.facility_name == facility.company_name,
                    MdOutreachPayload.status.in_(["READY", "CONTACTED"]),
                )
                .first()
            )
        if existing is not None:
            skipped += 1
            continue

        payload = build_and_persist_outreach_from_contact(db, facility, contact)
        payload_ids.append(str(payload.payload_id))
        generated += 1

    db.commit()
    return {
        "ready_contacts_scanned": len(rows),
        "payloads_generated": generated,
        "payloads_skipped": skipped,
        "payload_ids": payload_ids,
    }


def export_manus_outreach_queue(
    db: Session,
    *,
    limit: int = 50,
    sync_facility_contacts: bool = True,
) -> dict[str, Any]:
    if sync_facility_contacts:
        sync_ready_facility_contacts_to_outreach(db, limit=limit)

    rows = (
        db.query(MdOutreachPayload)
        .filter(MdOutreachPayload.status == "READY")
        .order_by(MdOutreachPayload.generated_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product": "VettedMe.ai Maryland B2B Outreach Sequencer",
        "count": len(rows),
        "manus_action": "Execute READY outreach payloads via configured email/SMS channels",
        "payloads": [
            {
                "payload_id": str(row.payload_id),
                "lead_id": str(row.lead_id) if row.lead_id else None,
                "facility_contact_id": str(row.facility_contact_id)
                if row.facility_contact_id
                else None,
                "facility_name": row.facility_name,
                "decision_maker_name": row.decision_maker_name,
                "decision_maker_title": row.decision_maker_title,
                "direct_email": row.direct_email,
                "facility_county": row.facility_county,
                "facility_type": row.facility_type,
                "email_subject": row.email_subject,
                "email_body": row.email_body,
                "sms_body": row.sms_body,
                "channel": row.channel,
                "status": row.status,
                "source": "facility_contacts" if row.facility_contact_id else "b2b_raw_leads",
            }
            for row in rows
        ],
    }


def write_manus_outreach_snapshot(db: Session, path: Path | None = None) -> Path:
    repo = Path(__file__).resolve().parents[1]
    out = path or repo / "logs" / "manus" / "md_outreach_queue.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = export_manus_outreach_queue(db)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return out
