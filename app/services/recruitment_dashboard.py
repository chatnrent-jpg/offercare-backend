"""Admin + Manus recruitment dashboard — contracts, B2B leads, ingested shifts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import B2BRawLead, FacilityContract, IngestedOpenShift, MarylandFacility
from app.services.manus_recruitment import build_manus_recruitment_config
from data_engine.paths import (
    INCOMING_CONTRACTS_DIR,
    INCOMING_SHIFTS_DIR,
    RAW_LEADS_DIR,
    ensure_data_engine_dirs,
)


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _contract_row(row: FacilityContract, facility_name: str | None) -> dict[str, Any]:
    creds = {}
    if row.credential_requirements_json:
        try:
            creds = json.loads(row.credential_requirements_json)
        except json.JSONDecodeError:
            creds = {}
    return {
        "contract_id": str(row.contract_id),
        "facility_id": str(row.facility_id),
        "facility_name": facility_name,
        "contract_name": row.contract_name,
        "review_status": row.review_status,
        "dispatch_halted": row.dispatch_halted == "true",
        "bill_rate_hourly": float(row.bill_rate_hourly) if row.bill_rate_hourly is not None else None,
        "pay_rate_hourly": float(row.pay_rate_hourly) if row.pay_rate_hourly is not None else None,
        "margin_pct": float(row.margin_pct) if row.margin_pct is not None else None,
        "cancellation_notice_hours": int(row.cancellation_notice_hours)
        if row.cancellation_notice_hours is not None
        else None,
        "credential_requirements": creds,
        "review_reason": row.review_reason,
        "source_filename": row.source_filename,
        "parsed_at": _iso(row.parsed_at),
    }


def build_recruitment_dashboard(db: Session, *, limit: int = 50) -> dict[str, Any]:
    ensure_data_engine_dirs()
    facilities = {
        str(row.facility_id): row.name
        for row in db.query(MarylandFacility.facility_id, MarylandFacility.name).all()
    }

    contracts = (
        db.query(FacilityContract)
        .order_by(FacilityContract.parsed_at.desc())
        .limit(limit)
        .all()
    )
    leads = db.query(B2BRawLead).order_by(B2BRawLead.imported_at.desc()).limit(limit).all()
    shifts = (
        db.query(IngestedOpenShift)
        .order_by(IngestedOpenShift.ingested_at.desc())
        .limit(limit)
        .all()
    )

    pending_review = sum(1 for row in contracts if row.review_status == "PENDING_EXECUTIVE_REVIEW")
    halted = sum(1 for row in contracts if row.dispatch_halted == "true")

    drop_zones = {
        "raw_leads_csv": sorted(p.name for p in RAW_LEADS_DIR.glob("*.csv")),
        "incoming_contracts": sorted(
            p.name
            for p in INCOMING_CONTRACTS_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".doc", ".txt", ".md"}
        ),
        "incoming_shifts_json": sorted(p.name for p in INCOMING_SHIFTS_DIR.glob("*.json")),
    }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "contracts_total": len(contracts),
            "contracts_pending_review": pending_review,
            "contracts_dispatch_halted": halted,
            "leads_total": len(leads),
            "shifts_ingested": len(shifts),
            "shifts_matched": sum(1 for row in shifts if row.status == "MATCHED"),
            "drop_zone_files": sum(len(v) for v in drop_zones.values()),
        },
        "drop_zones": drop_zones,
        "manus_config": build_manus_recruitment_config(),
        "contracts": [
            _contract_row(row, facilities.get(str(row.facility_id))) for row in contracts
        ],
        "leads": [
            {
                "lead_id": str(row.lead_id),
                "facility_name": row.facility_name,
                "contact_role": row.contact_role,
                "email_domain": row.email_domain,
                "procurement_urgency": row.procurement_urgency,
                "source_url": row.source_url,
                "contact_name": row.contact_name,
                "imported_at": _iso(row.imported_at),
            }
            for row in leads
        ],
        "ingested_shifts": [
            {
                "ingest_id": str(row.ingest_id),
                "facility_id": str(row.facility_id),
                "facility_name": facilities.get(str(row.facility_id)),
                "shift_date": row.shift_date,
                "unit_dept": row.unit_dept,
                "start_time": row.start_time,
                "shift_role": row.shift_role,
                "hourly_pay_rate": float(row.hourly_pay_rate),
                "status": row.status,
                "offer_id": str(row.offer_id) if row.offer_id else None,
                "ingested_at": _iso(row.ingested_at),
                "top_matches": _parse_matches(row.match_payload_json),
            }
            for row in shifts
        ],
    }


def _parse_matches(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    matches = payload.get("top_matches")
    return matches if isinstance(matches, list) else []


def build_manus_recruitment_snapshot(db: Session) -> dict[str, Any]:
    """Export artifact for Manus daily RFP/VMS briefing."""
    dashboard = build_recruitment_dashboard(db, limit=25)
    return {
        "schema_version": "1.0",
        "product": "VettedMe.ai Facility Recruitment Engine",
        "generated_at_utc": dashboard["generated_at_utc"],
        "summary": dashboard["summary"],
        "drop_zones": dashboard["drop_zones"],
        "manus_daily_prompt": (
            "Read recruitment_snapshot.json. Report: pending contract reviews, high-urgency "
            "B2B leads, unprocessed drop-zone files, and recommended Manus tasks for RFP "
            "monitoring and VMS shift sync. Do not override PENDING_EXECUTIVE_REVIEW contracts."
        ),
        "manus_workflows": dashboard["manus_config"]["manus_workflows"],
        "contracts_pending_review": [
            row for row in dashboard["contracts"] if row["review_status"] == "PENDING_EXECUTIVE_REVIEW"
        ],
        "high_urgency_leads": [
            row
            for row in dashboard["leads"]
            if str(row.get("procurement_urgency") or "").upper() in {"HIGH", "CRITICAL", "URGENT"}
        ],
        "recent_shifts": dashboard["ingested_shifts"][:10],
    }


def write_manus_recruitment_snapshot(
    db: Session,
    path: Path | None = None,
) -> Path:
    repo = Path(__file__).resolve().parents[2]
    out = path or repo / "logs" / "manus" / "recruitment_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_manus_recruitment_snapshot(db)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return out
