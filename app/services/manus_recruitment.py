"""Manus B2B recruitment workflows — external scrape handoff to Cursor data_engine."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from data_engine.lead_schema import OPTIONAL_LEAD_FIELDS, REQUIRED_LEAD_FIELDS
from data_engine.md_lead_schema import MD_OPTIONAL_LEAD_FIELDS, MD_REQUIRED_LEAD_FIELDS
from data_engine.paths import (
    INCOMING_CONTRACTS_DIR,
    INCOMING_SHIFTS_DIR,
    LEADS_DIR,
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
    ohcq_citation_csv = LEADS_DIR / "ohcq_staffing_citation_flags_md.csv"
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
            "ohcq_staffing_citation_csv": str(ohcq_citation_csv),
            "leads_dir": str(LEADS_DIR),
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
                "id": "ohcq-staffing-citation-tracker",
                "title": "Maryland OHCQ staffing citation tracker",
                "targets": [
                    "MDH Office of Health Care Quality (OHCQ) licensee directories",
                    "OHCQ long-term care and assisted living portal pages",
                    "CMS Nursing Home Health Citations (MD) — insufficient staffing tags",
                    "CMS Provider Info — below Maryland mandated nurse HPRD (3.76)",
                ],
                "command": "scripts/run-ohcq-citation-tracker.bat",
                "output": f"CSV -> {ohcq_citation_csv}",
                "required_columns": [
                    "facility_name",
                    "county",
                    "facility_type",
                    "flag_reason",
                    "deficiency_tag",
                    "deficiency_summary",
                    "survey_date",
                    "reported_nurse_hprd",
                    "state_mandated_hprd",
                    "source_portal",
                    "source_url",
                ],
                "manus_instructions": (
                    "Run the OHCQ citation tracker weekly. Sweep MDH OHCQ portals for SNF and ALF "
                    "licensee listings, cross-reference CMS health citations for insufficient staffing "
                    "shortages, and flag facilities below Maryland mandated care hours. Drop the CSV "
                    f"at {ohcq_citation_csv} for B2B outreach prioritization."
                ),
            },
            {
                "id": "clay-ohcq-don-hr-enrichment",
                "title": "Clay.com DON + HR Staffing Coordinator enrichment",
                "targets": [
                    "leads/ohcq_staffing_citation_flags_md.csv",
                    "Clay table webhook or api.clay.com/v3",
                    "LinkedIn person enrichment",
                    "Apollo / ZoomInfo corporate contact databases",
                ],
                "command": "scripts/clay_push_ohcq_leads.py",
                "config": "integrations/clay/ohcq_citation_enrichment.template.json",
                "output": f"CSV -> {LEADS_DIR / 'ohcq_staffing_citation_enriched_md.csv'}",
                "manus_instructions": (
                    "Copy integrations/clay/ohcq_citation_enrichment.template.json to "
                    "ohcq_citation_enrichment.json, set CLAY_TABLE_WEBHOOK_URL (or CLAY_TABLE_ID + "
                    "CLAY_SESSION_COOKIE + field IDs), then run scripts/clay_push_ohcq_leads.py. "
                    "Clay template auto-searches LinkedIn and corporate DBs for Director of Nursing "
                    "and HR Staffing Coordinator verified emails and direct phones per cited facility."
                ),
            },
            {
                "id": "md-ohcq-leads-pipeline-offline",
                "title": "MD OHCQ leads pipeline (offline build — no keys)",
                "targets": [
                    "leads/ohcq_staffing_citation_flags_md.csv",
                    "Clay staging enriched CSV",
                    "HeyReach import + sequence JSON",
                    "logs/manus/md_ohcq_leads_pipeline_manifest.json",
                ],
                "command": "scripts/run-md-ohcq-leads-pipeline.bat",
                "manus_instructions": (
                    "Run scripts/run-md-ohcq-leads-pipeline.bat to rebuild all offline artifacts. "
                    "Assign CLAY_* and HEYREACH_* keys on keys day; manifest tracks readiness."
                ),
            },
            {
                "id": "workstream-baltimore-cna-distribute",
                "title": "Workstream Baltimore CNA job distribution (Indeed + ZipRecruiter)",
                "targets": [
                    "/baltimore-instant-pay-cna/",
                    "Indeed + ZipRecruiter text-to-apply posts",
                    "caregiver_intake_queue webhook",
                ],
                "command": "scripts/workstream_distribute_baltimore_cna.py",
                "config": "integrations/workstream/baltimore_instant_pay_cna.template.json",
                "output": f"JSON -> {LEADS_DIR / 'workstream_baltimore_cna_job_posts.json'}",
                "manus_instructions": (
                    "Run scripts/run-workstream-baltimore-cna-distribute.bat --dry-run to preview. "
                    "Set WORKSTREAM_* credentials on keys day. Webhook /api/v1/webhooks/workstream/text-apply "
                    "routes Indeed/ZipRecruiter text replies into caregiver_intake_queue."
                ),
            },
            {
                "id": "heyreach-md-don-ohcq-sequence",
                "title": "HeyReach DON LinkedIn + email outreach (OHCQ staffing)",
                "targets": [
                    "leads/ohcq_staffing_citation_enriched_md.csv",
                    "HeyReach Lead List CSV import",
                    "LinkedIn connection request → message → email follow-up",
                ],
                "command": "scripts/heyreach_build_ohcq_sequence.py",
                "config": "integrations/heyreach/md_don_ohcq_outreach.template.json",
                "output": f"CSV -> {LEADS_DIR / 'heyreach_md_don_ohcq_import.csv'}",
                "manus_instructions": (
                    "Run scripts/run-heyreach-ohcq-sequence.bat after Clay enrichment. "
                    "Import heyreach_md_don_ohcq_import.csv into HeyReach, apply "
                    "heyreach_md_don_ohcq_sequence.json via UpdateSequence, and start campaign. "
                    "Copy dynamically inserts cited Maryland county names and focuses on "
                    "VettedCare.ai routing credentialed GNAs/LPNs to open shifts within 15 minutes."
                ),
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
