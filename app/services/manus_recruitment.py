"""Manus B2B recruitment workflows — external scrape handoff to Cursor data_engine."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from data_engine.lead_schema import OPTIONAL_LEAD_FIELDS, REQUIRED_LEAD_FIELDS
from data_engine.md_lead_schema import MD_OPTIONAL_LEAD_FIELDS, MD_REQUIRED_LEAD_FIELDS
from data_engine.paths import (
    INCOMING_CONTRACTS_DIR,
    INCOMING_SHIFTS_DIR,
    RAW_LEADS_DIR,
    ensure_data_engine_dirs,
)


def _base_url() -> str:
    configured = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    return configured or "http://127.0.0.1:8000"


def build_manus_recruitment_config() -> dict:
    ensure_data_engine_dirs()
    base = _base_url()
    prefix = f"{base}/api/vettedcare/manus/recruitment"
    repo = Path(__file__).resolve().parents[2]
    md_leads_path = RAW_LEADS_DIR / "md_facilities.csv"
    return {
        "product": "VettedCare.ai Maryland LTC Recruitment Engine",
        "architecture": "Manus acts (OHCQ/RFP/VMS) · VettedCare decides (parse, MBON gate, dispatch)",
        "market_focus": {
            "state": "MD",
            "facility_segments": ["SNF", "ALF", "HHA"],
            "clinician_roles": ["CNA", "GNA", "LPN"],
            "decision_makers": [
                "Facility Administrator",
                "Director of Nursing (DON)",
                "HR Director",
                "Staffing Coordinator",
            ],
        },
        "auth_header": "X-Manus-Key",
        "endpoints": {
            "config": f"{prefix}/config",
            "import_leads": f"{prefix}/leads/import",
            "import_md_facilities": f"{prefix}/leads/import-md",
            "submit_shifts": f"{prefix}/shifts",
            "process_contracts": f"{prefix}/contracts/process",
            "outreach_queue": f"{base}/api/vettedcare/recruitment/md-outreach-queue",
            "sync_facility_outreach": f"{base}/api/vettedcare/recruitment/md-outreach/sync-facilities",
        },
        "filesystem_handoff": {
            "raw_leads_csv": str(RAW_LEADS_DIR),
            "md_facilities_csv": str(md_leads_path),
            "incoming_contracts": str(INCOMING_CONTRACTS_DIR),
            "incoming_shifts_json": str(INCOMING_SHIFTS_DIR),
            "md_outreach_queue_json": str(repo / "logs" / "manus" / "md_outreach_queue.json"),
            "repo_root": str(repo),
        },
        "lead_csv_required_fields": list(REQUIRED_LEAD_FIELDS),
        "lead_csv_optional_fields": list(OPTIONAL_LEAD_FIELDS),
        "md_facilities_csv_required_fields": list(MD_REQUIRED_LEAD_FIELDS),
        "md_facilities_csv_optional_fields": list(MD_OPTIONAL_LEAD_FIELDS),
        "shift_json_required_fields": [
            "facility_id",
            "shift_date",
            "unit_dept",
            "start_time",
            "shift_role",
            "hourly_pay_rate",
        ],
        "manus_workflows": [
            {
                "id": "ohcq-facility-directory",
                "title": "Maryland OHCQ licensed facility scrape",
                "targets": [
                    "Maryland Department of Health OHCQ public directories",
                    "SNF / nursing home license lookup",
                    "Assisted living license lookup",
                    "Home health agency registry",
                ],
                "output": f"CSV -> {md_leads_path}",
                "required_columns": list(MD_REQUIRED_LEAD_FIELDS),
            },
            {
                "id": "b2b-executive-profiling",
                "title": "Administrator / DON / HR enrichment",
                "targets": ["LinkedIn public profiles", "Google Maps business listings"],
                "output": f"Append decision_maker_name, direct_email, facility_county to {md_leads_path}",
            },
            {
                "id": "rfp-rfq-monitor",
                "title": "Maryland healthcare staffing RFP monitor",
                "targets": [
                    "State healthcare procurement portals",
                    "SNF / ALF career directories",
                    "Home health staffing aggregators",
                ],
                "output": f"CSV -> {RAW_LEADS_DIR}",
            },
            {
                "id": "vms-open-shift-sync",
                "title": "VMS portal open-shift scrape",
                "targets": ["Fieldglass", "StaffReady", "ShiftWise"],
                "output": f"JSON batch -> POST {prefix}/shifts or drop in {INCOMING_SHIFTS_DIR}",
                "session_note": "Manus manages login cookies; VettedCare dedupes + MBON-gated matching locally",
            },
            {
                "id": "b2b-outreach-execution",
                "title": "Account-based outreach sequencer",
                "targets": [
                    "READY rows in facility_contacts (SNF) -> md_outreach_payloads",
                    "READY rows in md_outreach_queue.json",
                ],
                "output": "Send email/SMS using Cursor-generated payloads",
                "note": (
                    "POST /recruitment/md-outreach/sync-facilities after facility import, "
                    "then GET /recruitment/md-outreach-queue"
                ),
            },
        ],
        "safety_rules": {
            "contract_margin_gate": (
                "Maryland MSA contracts below regional bill floor or role margin -> REVIEW_MARGINS"
            ),
            "mbon_compliance_gate": (
                "CNA/GNA require GNA endorsement; LPN requires active MD or compact license; "
                "expiry within 30 days or sanctions -> REJECTED_COMPLIANCE"
            ),
            "shift_dedupe_key": "hash(facility_id + shift_date + unit_dept + start_time)",
            "matcher_limit": 3,
        },
    }
