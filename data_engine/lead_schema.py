"""B2B raw lead guardrails — Manus CSV → validated rows."""

from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import B2BRawLead

REQUIRED_LEAD_FIELDS = (
    "facility_name",
    "contact_role",
    "email_domain",
    "procurement_urgency",
    "source_url",
)

OPTIONAL_LEAD_FIELDS = (
    "contact_name",
    "contact_email",
    "state",
    "county",
    "notes",
    "manus_run_id",
)


@dataclass(frozen=True)
class LeadValidationError:
    row_number: int
    field: str
    message: str


def normalize_lead_row(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, val in raw.items():
        norm_key = str(key or "").strip().lower().replace(" ", "_")
        out[norm_key] = str(val or "").strip()
    return out


def validate_lead_row(row: dict[str, str], *, row_number: int) -> list[LeadValidationError]:
    errors: list[LeadValidationError] = []
    for field in REQUIRED_LEAD_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(
                LeadValidationError(
                    row_number=row_number,
                    field=field,
                    message=f"Missing required field: {field}",
                )
            )
    url = str(row.get("source_url") or "")
    if url and not (url.startswith("http://") or url.startswith("https://")):
        errors.append(
            LeadValidationError(
                row_number=row_number,
                field="source_url",
                message="source_url must be http(s)",
            )
        )
    return errors


def import_raw_leads_csv(
    db: Session,
    csv_path: Path,
    *,
    source: str = "manus",
) -> dict[str, Any]:
    """Load Manus-exported CSV from /data_engine/raw_leads/ into b2b_raw_leads."""
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    inserted = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for idx, raw in enumerate(reader, start=2):
            row = normalize_lead_row(raw)
            row_errors = validate_lead_row(row, row_number=idx)
            if row_errors:
                errors.extend([err.__dict__ for err in row_errors])
                skipped += 1
                continue

            existing = (
                db.query(B2BRawLead)
                .filter(
                    B2BRawLead.facility_name == row["facility_name"],
                    B2BRawLead.source_url == row["source_url"],
                    B2BRawLead.contact_role == row["contact_role"],
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            db.add(
                B2BRawLead(
                    lead_id=uuid.uuid4(),
                    facility_name=row["facility_name"],
                    contact_role=row["contact_role"],
                    email_domain=row["email_domain"],
                    procurement_urgency=row["procurement_urgency"],
                    source_url=row["source_url"],
                    contact_name=row.get("contact_name") or None,
                    contact_email=row.get("contact_email") or None,
                    state=row.get("state") or "MD",
                    county=row.get("county") or None,
                    notes=row.get("notes") or None,
                    manus_run_id=row.get("manus_run_id") or None,
                    source=source,
                    imported_at=datetime.now(timezone.utc),
                )
            )
            inserted += 1

    db.commit()
    return {
        "csv_path": str(csv_path),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
        "required_fields": list(REQUIRED_LEAD_FIELDS),
    }
