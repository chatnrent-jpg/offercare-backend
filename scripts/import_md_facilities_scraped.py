"""Import md_facilities_scraped.csv into PostgreSQL facilities + facility_contacts.

Normalization logic is shared with the prior dry-run pass. Live load uses
INSERT ... ON CONFLICT upserts inside a single transaction (all-or-nothing).
"""

from __future__ import annotations

import csv
import re
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CSV_PATH = REPO_ROOT / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"

VALID_FACILITY_TYPES = frozenset({"SNF", "ALF"})
VALID_CONTACT_ROLES = frozenset({"ADMINISTRATOR"})

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
}

UPSERT_FACILITY_SQL = """
INSERT INTO facilities (
    facility_id,
    company_name,
    facility_type,
    md_license_number,
    md_license_status,
    md_county,
    state,
    source,
    created_at,
    updated_at
) VALUES (
    :facility_id,
    :company_name,
    CAST(:facility_type AS facility_type_enum),
    :md_license_number,
    :md_license_status,
    :md_county,
    :state,
    :source,
    now(),
    now()
)
ON CONFLICT (md_license_number) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    facility_type = EXCLUDED.facility_type,
    md_county = EXCLUDED.md_county,
    md_license_status = EXCLUDED.md_license_status,
    updated_at = now()
RETURNING facility_id
"""

UPSERT_CONTACT_SQL = """
INSERT INTO facility_contacts (
    contact_id,
    facility_id,
    full_name,
    contact_role,
    email,
    outreach_status,
    created_at,
    updated_at
) VALUES (
    :contact_id,
    :facility_id,
    CAST(:full_name AS varchar),
    CAST(:contact_role AS facility_contact_role_enum),
    :email,
    CAST(:outreach_status AS outreach_status_enum),
    now(),
    now()
)
ON CONFLICT (facility_id, email) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    contact_role = EXCLUDED.contact_role,
    outreach_status = EXCLUDED.outreach_status,
    updated_at = now()
RETURNING contact_id
"""


def normalize_facility_type(raw: str) -> str | None:
    token = str(raw or "").strip().upper()
    if token in VALID_FACILITY_TYPES:
        return token
    return FACILITY_TYPE_ALIASES.get(token)


def normalize_contact_role(raw: str) -> str:
    token = str(raw or "").strip().upper()
    if token in VALID_CONTACT_ROLES:
        return token
    if "ADMIN" in token:
        return "ADMINISTRATOR"
    return "ADMINISTRATOR"


def normalize_county(raw: str) -> str:
    token = str(raw or "").strip()
    return re.sub(r"\s+county\s*$", "", token, flags=re.IGNORECASE).strip()


def outreach_status_for_type(facility_type: str) -> str:
    return "READY" if facility_type == "SNF" else "PENDING"


def _validate_enum_tokens(facility_type: str, contact_role: str) -> None:
    if facility_type not in VALID_FACILITY_TYPES:
        raise ValueError(f"ENUM mismatch facility_type: {facility_type!r}")
    if contact_role not in VALID_CONTACT_ROLES:
        raise ValueError(f"ENUM mismatch contact_role: {contact_role!r}")


def _parse_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    required_headers = {
        "facility_name",
        "facility_type",
        "md_license_number",
        "county",
        "contact_name",
        "contact_role",
        "contact_email",
    }

    rows: list[dict[str, Any]] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required_headers.issubset(set(reader.fieldnames)):
            missing = required_headers - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing headers: {sorted(missing)}")

        for row_number, raw in enumerate(reader, start=2):
            facility_name = str(raw.get("facility_name") or "").strip()
            facility_type = normalize_facility_type(str(raw.get("facility_type") or ""))
            license_no = str(raw.get("md_license_number") or "").strip()
            county = normalize_county(str(raw.get("county") or ""))
            contact_name = str(raw.get("contact_name") or "").strip()
            contact_role = normalize_contact_role(str(raw.get("contact_role") or ""))
            contact_email = str(raw.get("contact_email") or "").strip().lower()

            if not facility_name or not facility_type or not county:
                raise ValueError(f"row {row_number}: missing facility_name, facility_type, or county")
            if not license_no:
                raise ValueError(f"row {row_number}: missing md_license_number (required for upsert key)")
            if not contact_email or "@" not in contact_email:
                raise ValueError(f"row {row_number}: missing or invalid contact_email")

            _validate_enum_tokens(facility_type, contact_role)

            rows.append(
                {
                    "row_number": row_number,
                    "facility_name": facility_name,
                    "facility_type": facility_type,
                    "md_license_number": license_no,
                    "county": county,
                    "contact_name": contact_name or f"Administrator — {facility_name[:60]}",
                    "contact_role": contact_role,
                    "contact_email": contact_email,
                    "outreach_status": outreach_status_for_type(facility_type),
                }
            )

    if not rows:
        raise ValueError("CSV contains no data rows")

    return rows


def run_live_import(csv_path: Path = CSV_PATH) -> int:
    from sqlalchemy import create_engine, text

    from app.config import settings

    database_url = str(settings.DATABASE_URL or "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL is not set (check .env)", file=sys.stderr)
        return 1

    rows = _parse_csv_rows(csv_path)
    engine = create_engine(database_url, pool_pre_ping=True)

    print("LIVE IMPORT — PostgreSQL upsert (single transaction)")
    print(f"Source: {csv_path}")
    print(f"Rows: {len(rows)}")
    print("-" * 72)

    connection = engine.connect()
    transaction = connection.begin()
    try:
        for row in rows:
            facility_result = connection.execute(
                text(UPSERT_FACILITY_SQL),
                {
                    "facility_id": str(uuid.uuid4()),
                    "company_name": row["facility_name"],
                    "facility_type": row["facility_type"],
                    "md_license_number": row["md_license_number"],
                    "md_license_status": "ACTIVE",
                    "md_county": row["county"],
                    "state": "MD",
                    "source": "md_facilities_scraped_csv",
                },
            )
            facility_id = facility_result.scalar_one()

            connection.execute(
                text(UPSERT_CONTACT_SQL),
                {
                    "contact_id": str(uuid.uuid4()),
                    "facility_id": str(facility_id),
                    "full_name": row["contact_name"],
                    "contact_role": row["contact_role"],
                    "email": row["contact_email"],
                    "outreach_status": row["outreach_status"],
                },
            )

            print(
                "Imported -> "
                f"Facility: {row['facility_name']} | "
                f"Type: {row['facility_type']} | "
                f"License: {row['md_license_number']} | "
                f"County: {row['county']} | "
                f"Contact: {row['contact_name']} | "
                f"Role: {row['contact_role']} | "
                f"Email: {row['contact_email']}"
            )

        transaction.commit()
    except Exception as exc:
        transaction.rollback()
        print(f"ROLLBACK — import aborted: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()

    print("-" * 72)
    print(f"SUCCESS — committed {len(rows)} facility/contact pair(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_live_import())
