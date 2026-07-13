"""Staging-only B2B outreach manifest for Manus — no live execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MdFacilityContact, MdMarketFacility

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING_MANIFEST_PATH = REPO_ROOT / "logs" / "manus" / "md_outreach_queue.json"


def _salutation(contact: MdFacilityContact | None, company_name: str) -> str:
    if contact and contact.full_name:
        return contact.full_name.split()[0]
    return "Administrator"


def _admin_addressee(contact: MdFacilityContact | None) -> str:
    if contact and contact.contact_role == "ADMINISTRATOR":
        return contact.full_name or "Facility Administrator"
    return "Facility Administrator"


def _build_staging_copy(
    facility: MdMarketFacility,
    contact: MdFacilityContact | None,
) -> dict[str, str]:
    facility_type = str(facility.facility_type or "SNF").upper()
    county = facility.md_county
    facility_name = facility.company_name
    first = _salutation(contact, facility_name)
    addressee = _admin_addressee(contact)
    agency = settings.OUTREACH_AGENCY_NAME or "VettedMe.ai"
    sender = settings.OUTREACH_SENDER_NAME or "VettedMe Team"

    if facility_type == "SNF":
        compliance_hook = (
            "Maryland-specific GNA compliance firewall — every CNA is MBON-verified "
            "with an active GNA endorsement before they appear in your staffing queue"
        )
        subject = f"{facility_name} — GNA-compliant CNA/LPN coverage for {county} County SNF operations"
        body_intro = (
            f"Dear {addressee},\n\n"
            f"I'm {sender} at {agency}. We partner with skilled nursing leaders across {county} "
            f"to place MBON-cleared CNA, GNA, and LPN staff without the credential surprises "
            f"that stall admissions and force last-minute agency swaps."
        )
        body_value = (
            f"VettedMe.ai's {compliance_hook}.\n\n"
            f"For {facility_name}, that means:\n"
            f"• Pre-shift GNA endorsement verification for every CNA placement\n"
            f"• Lookahead matching that blocks non-compliant profiles before they reach your floor\n"
            f"• County-aware routing across the {county} SNF network\n"
            f"• Reduced survey and staffing-liability exposure from credential gaps"
        )
    else:
        compliance_hook = (
            "Maryland licensure compliance gate — clinicians are MBON-verified before dispatch"
        )
        subject = f"{facility_name} — compliant caregiver staffing support in {county} County"
        body_intro = (
            f"Dear {addressee},\n\n"
            f"I'm {sender} at {agency}. We support assisted living and home-health operators "
            f"across {county} with dependable CNA and LPN coverage backed by automated "
            f"Maryland Board of Nursing verification."
        )
        body_value = (
            f"Our platform applies a {compliance_hook}.\n\n"
            f"For {facility_name}, that means:\n"
            f"• Verified credentials before any caregiver is presented\n"
            f"• Regional matching optimized for {county}\n"
            f"• A single staffing desk for surge and planned coverage"
        )

    email_body = (
        f"{body_intro}\n\n"
        f"{body_value}\n\n"
        f"I would welcome 15 minutes to walk through how our Maryland GNA compliance firewall "
        f"can reduce your staffing friction this quarter. Reply to this note and we will "
        f"coordinate a brief call at your convenience.\n\n"
        f"— {sender}\n{agency}\n"
        f"Staging outreach · Not for live send until operations sign-off"
    )

    sms_body = (
        f"{agency}: Hi {first} — {agency} places MBON-verified staff in {county} with our "
        f"Maryland GNA compliance firewall. Reply YES for a staging coverage brief for "
        f"{facility_name}."
    )[:320]

    return {
        "email_subject": subject,
        "email_body": email_body,
        "sms_body": sms_body,
        "compliance_hook": compliance_hook,
    }


def build_staging_outreach_manifest(db: Session) -> dict[str, Any]:
    """Build staging manifest for all imported facilities — REVIEW_ONLY, no live send."""
    facilities = (
        db.query(MdMarketFacility)
        .order_by(MdMarketFacility.company_name.asc())
        .all()
    )
    payloads: list[dict[str, Any]] = []

    for facility in facilities:
        contact = (
            db.query(MdFacilityContact)
            .filter(MdFacilityContact.facility_id == facility.facility_id)
            .order_by(MdFacilityContact.contact_role.asc())
            .first()
        )
        copy = _build_staging_copy(facility, contact)
        payloads.append(
            {
                "payload_id": f"staging-{facility.facility_id}",
                "facility_id": str(facility.facility_id),
                "facility_contact_id": str(contact.contact_id) if contact else None,
                "facility_name": facility.company_name,
                "facility_type": facility.facility_type,
                "md_license_number": facility.md_license_number,
                "facility_county": facility.md_county,
                "decision_maker_name": contact.full_name if contact else None,
                "decision_maker_title": "Facility Administrator",
                "contact_role": contact.contact_role if contact else "ADMINISTRATOR",
                "direct_email": contact.email if contact else None,
                "email_subject": copy["email_subject"],
                "email_body": copy["email_body"],
                "sms_body": copy["sms_body"],
                "compliance_hook": copy["compliance_hook"],
                "channel": "EMAIL",
                "status": "STAGING",
                "live_execution": False,
                "manus_action": "REVIEW_ONLY — do not send until staging sign-off",
                "source": "facility_contacts",
            }
        )

    return {
        "mode": "STAGING",
        "live_execution": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product": "VettedMe.ai Maryland B2B Outreach — Staging Queue",
        "manus_action": "REVIEW_ONLY — read templates, do not dispatch email or SMS",
        "count": len(payloads),
        "payloads": payloads,
    }


def write_staging_outreach_manifest(
    db: Session,
    path: Path | None = None,
) -> Path:
    out = path or STAGING_MANIFEST_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_staging_outreach_manifest(db)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return out
