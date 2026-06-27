"""Maryland OHCQ / Manus B2B lead import — SNF, ALF, HHA executive profiling."""

from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import B2BRawLead
from data_engine.lead_schema import LeadValidationError, normalize_lead_row, validate_lead_row
from data_engine.md_outreach_sequencer import build_and_persist_outreach_payload

MD_FACILITY_TYPES = frozenset({"SNF", "ALF", "HHA"})
MD_DECISION_MAKER_TITLES = frozenset(
    {
        "ADMINISTRATOR",
        "FACILITY ADMINISTRATOR",
        "DON",
        "DIRECTOR OF NURSING",
        "HR DIRECTOR",
        "HR",
        "PROCUREMENT",
        "STAFFING COORDINATOR",
    }
)

MD_REQUIRED_LEAD_FIELDS = (
    "facility_name",
    "facility_type",
    "md_license_status",
    "decision_maker_name",
    "decision_maker_title",
    "direct_email",
    "facility_county",
    "procurement_urgency",
    "source_url",
)

MD_OPTIONAL_LEAD_FIELDS = (
    "contact_role",
    "email_domain",
    "contact_name",
    "contact_email",
    "state",
    "county",
    "notes",
    "manus_run_id",
    "facility_phone",
)


@dataclass(frozen=True)
class MdLeadValidationError:
    row_number: int
    field: str
    message: str


def _derive_email_domain(direct_email: str) -> str:
    token = str(direct_email or "").strip().lower()
    if "@" not in token:
        return token
    return token.split("@", 1)[1]


def _derive_contact_role(row: dict[str, str]) -> str:
    explicit = str(row.get("contact_role") or "").strip()
    if explicit:
        return explicit.upper()
    title = str(row.get("decision_maker_title") or "").strip().upper()
    if "DON" in title or "DIRECTOR OF NURSING" in title:
        return "DON"
    if "ADMINISTRATOR" in title:
        return "FACILITY_ADMINISTRATOR"
    if "HR" in title or "PROCUREMENT" in title:
        return "HR_DIRECTOR"
    if "STAFFING" in title:
        return "STAFFING_COORDINATOR"
    return title or "FACILITY_ADMINISTRATOR"


def validate_md_lead_row(row: dict[str, str], *, row_number: int) -> list[MdLeadValidationError]:
    errors: list[MdLeadValidationError] = []
    for field in MD_REQUIRED_LEAD_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(
                MdLeadValidationError(
                    row_number=row_number,
                    field=field,
                    message=f"Missing required Maryland field: {field}",
                )
            )

    facility_type = str(row.get("facility_type") or "").strip().upper()
    if facility_type and facility_type not in MD_FACILITY_TYPES:
        errors.append(
            MdLeadValidationError(
                row_number=row_number,
                field="facility_type",
                message=f"facility_type must be one of {sorted(MD_FACILITY_TYPES)}",
            )
        )

    email = str(row.get("direct_email") or "").strip()
    if email and "@" not in email:
        errors.append(
            MdLeadValidationError(
                row_number=row_number,
                field="direct_email",
                message="direct_email must contain @",
            )
        )

    url = str(row.get("source_url") or "")
    if url and not (url.startswith("http://") or url.startswith("https://")):
        errors.append(
            MdLeadValidationError(
                row_number=row_number,
                field="source_url",
                message="source_url must be http(s)",
            )
        )

    # Backward-compatible guardrails when Manus omits legacy fields
    legacy = validate_lead_row(
        {
            "facility_name": row.get("facility_name", ""),
            "contact_role": _derive_contact_role(row),
            "email_domain": row.get("email_domain") or _derive_email_domain(email),
            "procurement_urgency": row.get("procurement_urgency", ""),
            "source_url": row.get("source_url", ""),
        },
        row_number=row_number,
    )
    for err in legacy:
        errors.append(MdLeadValidationError(row_number=err.row_number, field=err.field, message=err.message))

    return errors


def import_md_facilities_csv(
    db: Session,
    csv_path: Path,
    *,
    source: str = "manus_ohcq",
    generate_outreach: bool = True,
) -> dict[str, Any]:
    """Load Manus OHCQ / LinkedIn export from data_engine/raw_leads/md_facilities.csv."""
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    inserted = 0
    skipped = 0
    outreach_generated = 0
    errors: list[dict[str, Any]] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for idx, raw in enumerate(reader, start=2):
            row = normalize_lead_row(raw)
            row_errors = validate_md_lead_row(row, row_number=idx)
            if row_errors:
                errors.extend([err.__dict__ for err in row_errors])
                skipped += 1
                continue

            facility_type = str(row["facility_type"]).strip().upper()
            direct_email = str(row["direct_email"]).strip().lower()
            facility_county = str(row["facility_county"]).strip()
            contact_role = _derive_contact_role(row)
            email_domain = str(row.get("email_domain") or _derive_email_domain(direct_email)).strip().lower()

            existing = (
                db.query(B2BRawLead)
                .filter(
                    B2BRawLead.facility_name == row["facility_name"],
                    B2BRawLead.direct_email == direct_email,
                    B2BRawLead.facility_type == facility_type,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            lead = B2BRawLead(
                lead_id=uuid.uuid4(),
                facility_name=row["facility_name"],
                contact_role=contact_role,
                email_domain=email_domain,
                procurement_urgency=row["procurement_urgency"],
                source_url=row["source_url"],
                contact_name=row.get("decision_maker_name") or row.get("contact_name") or None,
                contact_email=direct_email,
                state=row.get("state") or "MD",
                county=facility_county or row.get("county") or None,
                notes=row.get("notes") or None,
                manus_run_id=row.get("manus_run_id") or None,
                source=source,
                imported_at=datetime.now(timezone.utc),
                facility_type=facility_type,
                md_license_status=str(row["md_license_status"]).strip().upper(),
                decision_maker_name=str(row["decision_maker_name"]).strip(),
                decision_maker_title=str(row["decision_maker_title"]).strip(),
                direct_email=direct_email,
                facility_county=facility_county,
                outreach_ready="false",
            )
            db.add(lead)
            db.flush()

            if generate_outreach and str(row.get("md_license_status", "")).upper() in {
                "ACTIVE",
                "LICENSED",
                "CURRENT",
            }:
                build_and_persist_outreach_payload(db, lead)
                lead.outreach_ready = "true"
                outreach_generated += 1

            inserted += 1

    db.commit()
    return {
        "csv_path": str(csv_path),
        "inserted": inserted,
        "skipped": skipped,
        "outreach_generated": outreach_generated,
        "errors": errors,
        "required_fields": list(MD_REQUIRED_LEAD_FIELDS),
        "target_segments": sorted(MD_FACILITY_TYPES),
        "decision_maker_personas": sorted(MD_DECISION_MAKER_TITLES),
    }
