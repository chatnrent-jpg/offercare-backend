"""Import scraped Maryland B2B leads into facilities + facility_contacts tables."""

from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import MdFacilityContact, MdMarketFacility, MarylandFacility

SCRAPED_CSV_DEFAULT = Path(__file__).resolve().parents[1] / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"

VALID_FACILITY_TYPES = frozenset({"SNF", "ALF", "HHA"})
VALID_CONTACT_ROLES = frozenset({"ADMINISTRATOR", "DON", "HR_HEAD"})

FACILITY_TYPE_ALIASES = {
    "SNF": "SNF",
    "SKILLED NURSING": "SNF",
    "SKILLED NURSING FACILITY": "SNF",
    "NURSING HOME": "SNF",
    "LONG TERM CARE": "SNF",
    "LTC": "SNF",
    "ALF": "ALF",
    "ASSISTED LIVING": "ALF",
    "ASSISTED LIVING FACILITY": "ALF",
    "HHA": "HHA",
    "HOME HEALTH": "HHA",
    "HOME HEALTH AGENCY": "HHA",
}


def _normalize_facility_type(raw: str) -> str | None:
    token = str(raw or "").strip().upper()
    if token in VALID_FACILITY_TYPES:
        return token
    return FACILITY_TYPE_ALIASES.get(token)


def _normalize_county(raw: str) -> str:
    import re

    token = str(raw or "").strip()
    token = re.sub(r"\s+county\s*$", "", token, flags=re.IGNORECASE).strip()
    return token


def _normalize_contact_role(raw: str) -> str:
    token = str(raw or "").strip().upper()
    if token in VALID_CONTACT_ROLES:
        return token
    if "DON" in token or "DIRECTOR OF NURSING" in token:
        return "DON"
    if "HR" in token:
        return "HR_HEAD"
    return "ADMINISTRATOR"


def _resolve_maryland_facility_id(db: Session, company_name: str) -> uuid.UUID | None:
    from app.services.job_board_crisis_scraper import match_facility_name

    candidates = db.query(MarylandFacility).filter(MarylandFacility.state == "MD").all()
    matched = match_facility_name(company_name, candidates)
    return matched.facility_id if matched is not None else None


def _outreach_status_for_type(facility_type: str) -> str:
    return "READY" if str(facility_type).upper() == "SNF" else "PENDING"


def _normalize_name_key(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _find_existing_facility(
    db: Session,
    *,
    company_name: str,
    license_no: str,
    county: str,
) -> tuple[MdMarketFacility | None, str | None]:
    """Composite duplicate check: cross-match license number and facility name."""
    by_license: MdMarketFacility | None = None
    by_name: MdMarketFacility | None = None

    if license_no:
        by_license = (
            db.query(MdMarketFacility)
            .filter(MdMarketFacility.md_license_number == license_no)
            .first()
        )

    by_name = (
        db.query(MdMarketFacility)
        .filter(
            MdMarketFacility.company_name == company_name,
            MdMarketFacility.md_county == county,
        )
        .first()
    )

    if by_license and by_name and by_license.facility_id != by_name.facility_id:
        return None, "duplicate_conflict:license_and_name_point_to_different_rows"

    candidate = by_license or by_name
    if candidate is None:
        return None, None

    if by_license and _normalize_name_key(by_license.company_name) != _normalize_name_key(company_name):
        return None, "duplicate_conflict:license_number_name_mismatch"

    if by_name and license_no and by_name.md_license_number and by_name.md_license_number != license_no:
        return None, "duplicate_conflict:facility_name_license_mismatch"

    return candidate, None


def import_scraped_facilities_csv(
    db: Session,
    csv_path: Path | None = None,
    *,
    source: str = "mhcc_scrape",
    generate_outreach: bool = True,
) -> dict[str, Any]:
    """Load md_facilities_scraped.csv into facilities + facility_contacts."""
    path = csv_path or SCRAPED_CSV_DEFAULT
    if not path.is_file():
        raise FileNotFoundError(str(path))

    now = datetime.now(timezone.utc)
    inserted_facilities = 0
    updated_facilities = 0
    inserted_contacts = 0
    updated_contacts = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    rows_out: list[dict[str, Any]] = []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for idx, raw in enumerate(reader, start=2):
            company_name = str(raw.get("facility_name") or "").strip()
            facility_type = _normalize_facility_type(str(raw.get("facility_type") or ""))
            license_no = str(raw.get("md_license_number") or "").strip()
            county = _normalize_county(str(raw.get("county") or ""))
            contact_name = str(raw.get("contact_name") or "").strip()
            contact_role = _normalize_contact_role(str(raw.get("contact_role") or ""))
            contact_email = str(raw.get("contact_email") or "").strip().lower()

            if not company_name or not facility_type or not county:
                errors.append({"row": idx, "error": "missing_required_fields"})
                skipped += 1
                continue
            if facility_type not in VALID_FACILITY_TYPES:
                errors.append({"row": idx, "error": f"invalid_facility_type:{facility_type}"})
                skipped += 1
                continue

            facility, conflict = _find_existing_facility(
                db,
                company_name=company_name,
                license_no=license_no,
                county=county,
            )
            if conflict:
                errors.append({"row": idx, "error": conflict, "facility_name": company_name})
                skipped += 1
                continue

            spine_id = _resolve_maryland_facility_id(db, company_name)
            if facility is None:
                facility = MdMarketFacility(
                    facility_id=uuid.uuid4(),
                    company_name=company_name,
                    facility_type=facility_type,
                    md_license_number=license_no or None,
                    md_license_status="ACTIVE",
                    md_county=county,
                    state="MD",
                    maryland_facility_id=spine_id,
                    source=source,
                    created_at=now,
                    updated_at=now,
                )
                db.add(facility)
                inserted_facilities += 1
            else:
                facility.company_name = company_name
                facility.facility_type = facility_type
                facility.md_license_number = license_no or facility.md_license_number
                facility.md_license_status = "ACTIVE"
                facility.md_county = county
                if spine_id is not None:
                    facility.maryland_facility_id = spine_id
                facility.updated_at = now
                updated_facilities += 1

            db.flush()

            contact = None
            if contact_email:
                contact = (
                    db.query(MdFacilityContact)
                    .filter(
                        MdFacilityContact.facility_id == facility.facility_id,
                        MdFacilityContact.email == contact_email,
                    )
                    .first()
                )
            if contact is None:
                contact = (
                    db.query(MdFacilityContact)
                    .filter(
                        MdFacilityContact.facility_id == facility.facility_id,
                        MdFacilityContact.contact_role == contact_role,
                    )
                    .first()
                )

            outreach_status = _outreach_status_for_type(facility_type)
            if contact is None:
                contact = MdFacilityContact(
                    contact_id=uuid.uuid4(),
                    facility_id=facility.facility_id,
                    full_name=contact_name or f"{contact_role} — {company_name[:60]}",
                    contact_role=contact_role,
                    email=contact_email or None,
                    outreach_status=outreach_status,
                    created_at=now,
                    updated_at=now,
                )
                db.add(contact)
                inserted_contacts += 1
            else:
                contact.full_name = contact_name or contact.full_name
                contact.contact_role = contact_role
                if contact_email:
                    contact.email = contact_email
                contact.outreach_status = outreach_status
                contact.updated_at = now
                updated_contacts += 1

            rows_out.append(
                {
                    "facility_id": str(facility.facility_id),
                    "company_name": facility.company_name,
                    "facility_type": facility.facility_type,
                    "md_county": facility.md_county,
                    "maryland_facility_id": str(facility.maryland_facility_id)
                    if facility.maryland_facility_id
                    else None,
                    "contact_email": contact.email,
                    "outreach_status": contact.outreach_status,
                }
            )

    db.commit()

    outreach_sync: dict[str, Any] | None = None
    if generate_outreach:
        from data_engine.md_outreach_sequencer import sync_ready_facility_contacts_to_outreach

        outreach_sync = sync_ready_facility_contacts_to_outreach(db)

    return {
        "csv_path": str(path),
        "inserted_facilities": inserted_facilities,
        "updated_facilities": updated_facilities,
        "inserted_contacts": inserted_contacts,
        "updated_contacts": updated_contacts,
        "skipped": skipped,
        "errors": errors,
        "rows": rows_out,
        "outreach_sync": outreach_sync,
    }


def list_facilities_with_contacts(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    facilities = (
        db.query(MdMarketFacility)
        .order_by(MdMarketFacility.company_name.asc())
        .limit(limit)
        .all()
    )
    out: list[dict[str, Any]] = []
    for facility in facilities:
        contacts = (
            db.query(MdFacilityContact)
            .filter(MdFacilityContact.facility_id == facility.facility_id)
            .all()
        )
        primary = contacts[0] if contacts else None
        out.append(
            {
                "facility_id": str(facility.facility_id),
                "facility_name": facility.company_name,
                "facility_type": facility.facility_type,
                "md_license_number": facility.md_license_number,
                "county": facility.md_county,
                "md_license_status": facility.md_license_status,
                "contact_name": primary.full_name if primary else None,
                "contact_role": primary.contact_role if primary else None,
                "contact_email": primary.email if primary else None,
                "outreach_status": primary.outreach_status if primary else None,
                "maryland_facility_id": str(facility.maryland_facility_id)
                if facility.maryland_facility_id
                else None,
            }
        )
    return out


def verify_imported_facilities(db: Session, *, expected: int | None = None) -> dict[str, Any]:
    """Post-import verification — counts and ENUM token audit."""
    facilities = db.query(MdMarketFacility).order_by(MdMarketFacility.company_name.asc()).all()
    contacts = db.query(MdFacilityContact).count()
    type_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    outreach_counts: dict[str, int] = {}
    invalid_types: list[str] = []
    invalid_roles: list[str] = []

    for facility in facilities:
        ft = str(facility.facility_type or "")
        type_counts[ft] = type_counts.get(ft, 0) + 1
        if ft not in VALID_FACILITY_TYPES:
            invalid_types.append(ft)

    for contact in db.query(MdFacilityContact).all():
        role = str(contact.contact_role or "")
        status = str(contact.outreach_status or "")
        role_counts[role] = role_counts.get(role, 0) + 1
        outreach_counts[status] = outreach_counts.get(status, 0) + 1
        if role not in VALID_CONTACT_ROLES:
            invalid_roles.append(role)

    ok = not invalid_types and not invalid_roles
    if expected is not None:
        ok = ok and len(facilities) >= expected

    return {
        "ok": ok,
        "facility_count": len(facilities),
        "contact_count": contacts,
        "expected_facilities": expected,
        "facility_type_counts": type_counts,
        "contact_role_counts": role_counts,
        "outreach_status_counts": outreach_counts,
        "invalid_facility_types": invalid_types,
        "invalid_contact_roles": invalid_roles,
        "facilities": [
            {
                "company_name": f.company_name,
                "facility_type": f.facility_type,
                "md_license_number": f.md_license_number,
                "md_county": f.md_county,
            }
            for f in facilities
        ],
    }
