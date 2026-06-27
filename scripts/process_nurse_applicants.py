"""Simulate Maryland nurse applicant registration — staging compliance pipeline.

Processes mock applicants through MarylandComplianceValidator rules:
  - 30-day license expiry buffer
  - SNF + CNA requires GNA endorsement

Writes results to logs/manus/processed_providers.json (staging only).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_PATH = REPO_ROOT / "logs" / "manus" / "processed_providers.json"

# Mock applicants registering for Maryland work (staging payloads).
MOCK_APPLICANTS: list[dict[str, Any]] = [
    {
        "name": "Aisha Thompson",
        "license_type": "CNA",
        "license_number": "CNA-MD-88421",
        "has_gna_endorsement": True,
        "county": "Montgomery",
        "verification_timestamp": "2026-06-20T14:30:00+00:00",
        "license_expires_on": "2027-03-15T00:00:00+00:00",
        "target_facility_type": "SNF",
    },
    {
        "name": "Brian Okafor",
        "license_type": "CNA",
        "license_number": "CNA-MD-77219",
        "has_gna_endorsement": False,
        "county": "Baltimore",
        "verification_timestamp": "2026-06-21T09:15:00+00:00",
        "license_expires_on": "2027-01-10T00:00:00+00:00",
        "target_facility_type": "SNF",
    },
    {
        "name": "Carmen Delgado",
        "license_type": "LPN",
        "license_number": "LPN-MD-55290",
        "has_gna_endorsement": False,
        "county": "Baltimore",
        "verification_timestamp": "2026-06-19T16:45:00+00:00",
        "license_expires_on": "2027-06-01T00:00:00+00:00",
        "target_facility_type": "SNF",
        "mbon_status": "ACTIVE",
    },
    {
        "name": "Derek Washington",
        "license_type": "CNA",
        "license_number": "CNA-MD-66104",
        "has_gna_endorsement": True,
        "county": "Prince George's",
        "verification_timestamp": "2026-06-22T11:00:00+00:00",
        "license_expires_on": (datetime.now(timezone.utc) + timedelta(days=18)).strftime(
            "%Y-%m-%dT00:00:00+00:00"
        ),
        "target_facility_type": "SNF",
    },
    {
        "name": "Elena Vasquez",
        "license_type": "CNA",
        "license_number": "CNA-MD-90331",
        "has_gna_endorsement": True,
        "county": "Anne Arundel",
        "verification_timestamp": "2026-06-18T08:20:00+00:00",
        "license_expires_on": (datetime.now(timezone.utc) + timedelta(days=120)).strftime(
            "%Y-%m-%dT00:00:00+00:00"
        ),
        "target_facility_type": "ALF",
    },
]


def _parse_ts(value: str) -> datetime:
    token = str(value).strip()
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def process_applicants(applicants: list[dict[str, Any]]) -> dict[str, Any]:
    from compliance.md_licensure_validator import (
        EXPIRY_BLOCK_DAYS,
        FacilityTarget,
        MarylandComplianceValidator,
        ProviderCompliancePayload,
    )

    validator = MarylandComplianceValidator()
    processed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, applicant in enumerate(applicants, start=1):
        try:
            name = str(applicant["name"])
            license_type = str(applicant["license_type"]).upper()
            license_number = str(applicant["license_number"])
            county = str(applicant["county"])
            has_gna = bool(applicant.get("has_gna_endorsement"))
            verification_ts = str(applicant["verification_timestamp"])
            target_ft = str(applicant.get("target_facility_type") or "SNF").upper()
            expires_raw = applicant.get("license_expires_on")

            expires_on = _parse_ts(str(expires_raw)) if expires_raw else None

            payload = ProviderCompliancePayload(
                credential_type=license_type,
                license_number=license_number,
                license_expires_on=expires_on,
                has_gna_endorsement=has_gna,
                home_county=county,
                mbon_status=str(applicant.get("mbon_status") or "ACTIVE"),
                ohcq_sanction_flag=bool(applicant.get("ohcq_sanction_flag")),
            )
            facility = FacilityTarget(facility_type=target_ft, county=county)
            result = validator.validate_for_facility(payload, facility)

            processed.append(
                {
                    "applicant_index": index,
                    "name": name,
                    "license_type": license_type,
                    "license_number": license_number,
                    "has_gna_endorsement": has_gna,
                    "county": county,
                    "verification_timestamp": verification_ts,
                    "target_facility_type": target_ft,
                    "license_expires_on": expires_on.isoformat() if expires_on else None,
                    "compliance_status": result.compliance_status,
                    "compliant": result.compliant,
                    "placement_eligible": result.compliant,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "days_to_expiry": result.days_to_expiry,
                    "rules_applied": {
                        "expiry_buffer_days": EXPIRY_BLOCK_DAYS,
                        "snf_cna_requires_gna": target_ft == "SNF" and license_type == "CNA",
                    },
                }
            )
        except Exception as exc:
            errors.append({"applicant_index": index, "error": exc.__class__.__name__, "detail": str(exc)})

    eligible = sum(1 for row in processed if row.get("placement_eligible"))

    return {
        "mode": "STAGING",
        "live_execution": False,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "product": "VettedCare.ai Nurse Applicant Pipeline",
        "applicant_count": len(applicants),
        "placement_eligible_count": eligible,
        "processing_errors": errors,
        "applicants": processed,
    }


def write_staging_output(payload: dict[str, Any], path: Path = OUTPUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def main() -> int:
    try:
        result = process_applicants(MOCK_APPLICANTS)
        out_path = write_staging_output(result)
        print(f"STAGING — wrote {result['applicant_count']} applicant record(s)")
        print(f"Placement eligible: {result['placement_eligible_count']}")
        print(f"Output: {out_path}")
        if result["processing_errors"]:
            print(f"Errors: {result['processing_errors']}", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"FATAL — pipeline aborted: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
