"""HeyReach outreach — Clay-enriched OHCQ leads → multi-channel DON sequence."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_engine.md_county_normalizer import normalize_md_county
from data_engine.paths import LEADS_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = REPO_ROOT / "integrations" / "heyreach" / "md_don_ohcq_outreach.template.json"
DEFAULT_ENRICHED_CSV = LEADS_DIR / "ohcq_staffing_citation_enriched_md.csv"
DEFAULT_FLAGS_CSV = LEADS_DIR / "ohcq_staffing_citation_flags_md.csv"
DEFAULT_IMPORT_CSV = LEADS_DIR / "heyreach_md_don_ohcq_import.csv"
DEFAULT_SEQUENCE_JSON = LEADS_DIR / "heyreach_md_don_ohcq_sequence.json"


@dataclass(frozen=True)
class HeyReachDonLead:
    facility_name: str
    county: str
    facility_type: str
    flag_reason: str
    don_full_name: str
    don_first_name: str
    don_last_name: str
    don_verified_email: str
    don_linkedin_url: str
    county_phrase: str
    compliance_hook: str
    linkedin_connection_message: str
    linkedin_follow_up_message: str
    email_subject: str
    email_body: str

    def to_import_row(self) -> dict[str, str]:
        return {
            "linkedin_url": self.don_linkedin_url,
            "first_name": self.don_first_name,
            "last_name": self.don_last_name,
            "email": self.don_verified_email,
            "company": self.facility_name,
            "custom_county": self.county,
            "custom_county_phrase": self.county_phrase,
            "custom_compliance_hook": self.compliance_hook,
            "custom_facility_name": self.facility_name,
            "custom_flag_reason": self.flag_reason,
            "custom_linkedin_connection": self.linkedin_connection_message,
            "custom_linkedin_followup": self.linkedin_follow_up_message,
            "custom_email_subject": self.email_subject,
            "custom_email_body": self.email_body,
        }


def load_heyreach_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("heyreach_config_must_be_object")
    return payload


def _split_name(full_name: str) -> tuple[str, str]:
    parts = str(full_name or "").strip().split()
    if not parts:
        return ("Director", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], parts[-1])


def county_phrase(county: str) -> str:
    normalized = normalize_md_county(county).normalized or str(county or "").strip()
    if not normalized:
        return "across Maryland"
    if normalized == "Baltimore City":
        return "in Baltimore City"
    if normalized.lower().endswith("county"):
        return f"in {normalized}"
    return f"in {normalized} County"


def compliance_hook(flag_reason: str, config: dict[str, Any] | None = None) -> str:
    reason = str(flag_reason or "").strip().lower()
    if "insufficient_staffing_citation" in reason:
        return "recent OHCQ/CMS staffing citation"
    if "below_state_mandated" in reason:
        return "state-mandated nurse hour shortfall"
    if "below_casemix" in reason:
        return "reported nurse hours below case-mix expectation"
    if "low_staffing_rating" in reason:
        return "CMS staffing rating pressure"
    return "staffing compliance pressure"


def _render_template(template: str, tokens: dict[str, str]) -> str:
    rendered = str(template or "")
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _message_tokens(lead_row: dict[str, str]) -> dict[str, str]:
    county = normalize_md_county(str(lead_row.get("county") or "")).normalized
    don_name = str(lead_row.get("don_full_name") or "Director").strip()
    first_name, _ = _split_name(don_name)
    return {
        "first_name": first_name,
        "don_first_name": first_name,
        "facility_name": str(lead_row.get("facility_name") or "your facility").strip(),
        "county": county,
        "county_phrase": county_phrase(county),
        "compliance_hook": compliance_hook(str(lead_row.get("flag_reason") or "")),
        "company_name": str(lead_row.get("facility_name") or "your facility").strip(),
        "sender_name": str(os.environ.get("OUTREACH_SENDER_NAME") or "VettedCare Team").strip(),
        "agency_name": str(os.environ.get("OUTREACH_AGENCY_NAME") or "VettedCare.ai").strip(),
    }


def render_messages_for_lead(
    lead_row: dict[str, str],
    *,
    config: dict[str, Any],
) -> dict[str, str]:
    templates = config.get("message_templates") or {}
    tokens = _message_tokens(lead_row)
    rendered: dict[str, str] = {}
    for key, spec in templates.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("subject") is not None:
            rendered[f"{key}.subject"] = _render_template(str(spec.get("subject") or ""), tokens)
            rendered[f"{key}.fallback_subject"] = _render_template(
                str(spec.get("fallback_subject") or spec.get("subject") or ""), tokens
            )
        rendered[f"{key}.body"] = _render_template(str(spec.get("body") or ""), tokens)
        rendered[f"{key}.fallback_body"] = _render_template(
            str(spec.get("fallback_body") or spec.get("body") or ""), tokens
        )
    return rendered


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _merge_key(row: dict[str, str]) -> tuple[str, str]:
    facility = re.sub(r"\s+", " ", str(row.get("facility_name") or "").strip().lower())
    county = re.sub(r"\s+", " ", str(row.get("county") or "").strip().lower())
    return (facility, county)


def read_clay_enriched_leads(
    *,
    enriched_path: Path | None = None,
    flags_path: Path | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    cfg = config or load_heyreach_config()
    input_cfg = cfg.get("input") or {}
    enriched = enriched_path or (REPO_ROOT / str((input_cfg.get("primary_source") or {}).get("path") or DEFAULT_ENRICHED_CSV.relative_to(REPO_ROOT)))
    flags = flags_path or (REPO_ROOT / str((input_cfg.get("fallback_source") or {}).get("path") or DEFAULT_FLAGS_CSV.relative_to(REPO_ROOT)))

    enriched_rows = _read_csv_rows(enriched)
    flags_rows = _read_csv_rows(flags)
    flags_by_key = {_merge_key(row): row for row in flags_rows}

    merged: list[dict[str, str]] = []
    source_rows = enriched_rows if enriched_rows else flags_rows
    for row in source_rows:
        key = _merge_key(row)
        base = dict(flags_by_key.get(key, {}))
        base.update({k: v for k, v in row.items() if str(v or "").strip()})
        if not str(base.get("facility_name") or "").strip():
            continue
        county_norm = normalize_md_county(str(base.get("county") or ""))
        if not county_norm.normalized:
            continue
        base["county"] = county_norm.normalized
        merged.append(base)
    return merged


def build_heyreach_don_leads(
    rows: list[dict[str, str]],
    *,
    config: dict[str, Any],
) -> list[HeyReachDonLead]:
    leads: list[HeyReachDonLead] = []
    for row in rows:
        messages = render_messages_for_lead(row, config=config)
        don_name = str(row.get("don_full_name") or "Director of Nursing").strip()
        first, last = _split_name(don_name)
        county = str(row.get("county") or "").strip()
        leads.append(
            HeyReachDonLead(
                facility_name=str(row.get("facility_name") or "").strip(),
                county=county,
                facility_type=str(row.get("facility_type") or "SNF").strip(),
                flag_reason=str(row.get("flag_reason") or "").strip(),
                don_full_name=don_name,
                don_first_name=first,
                don_last_name=last,
                don_verified_email=str(row.get("don_verified_email") or "").strip(),
                don_linkedin_url=str(row.get("don_linkedin_url") or "").strip(),
                county_phrase=county_phrase(county),
                compliance_hook=compliance_hook(str(row.get("flag_reason") or "")),
                linkedin_connection_message=messages.get("linkedin_connection_request.body", ""),
                linkedin_follow_up_message=messages.get("linkedin_follow_up_message.body", ""),
                email_subject=messages.get("email_follow_up.subject", ""),
                email_body=messages.get("email_follow_up.body", ""),
            )
        )
    return leads


def write_heyreach_import_csv(
    leads: list[HeyReachDonLead],
    output_path: Path | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> Path:
    cfg = config or load_heyreach_config()
    import_cfg = cfg.get("heyreach_import_csv") or {}
    destination = output_path or (REPO_ROOT / str(import_cfg.get("path") or DEFAULT_IMPORT_CSV.relative_to(REPO_ROOT)))
    destination.parent.mkdir(parents=True, exist_ok=True)

    columns = import_cfg.get("columns") or []
    fieldnames = [str(col.get("heyreach_field")) for col in columns if col.get("heyreach_field")]
    if not fieldnames:
        fieldnames = list(leads[0].to_import_row().keys()) if leads else ["linkedin_url", "first_name", "email"]

    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            row = lead.to_import_row()
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    logger.info("Wrote %s HeyReach import rows to %s", len(leads), destination)
    return destination


def resolve_sequence_tree(config: dict[str, Any], sample_messages: dict[str, str] | None = None) -> dict[str, Any]:
    """Replace template placeholders in sequence_tree with rendered sample or token keys."""
    tree = json.loads(json.dumps(config.get("sequence_tree") or {}))

    def _substitute(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: _substitute(value) for key, value in node.items()}
        if isinstance(node, list):
            return [_substitute(item) for item in node]
        if isinstance(node, str) and node.startswith("{{") and node.endswith("}}"):
            token = node[2:-2].strip()
            if sample_messages and token in sample_messages:
                return sample_messages[token]
            return node
        return node

    return _substitute(tree)


def write_sequence_json(
    config: dict[str, Any],
    *,
    sample_messages: dict[str, str] | None = None,
    output_path: Path | None = None,
) -> Path:
    export_cfg = config.get("export") or {}
    destination = output_path or (REPO_ROOT / str(export_cfg.get("sequence_json_path") or DEFAULT_SEQUENCE_JSON.relative_to(REPO_ROOT)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "campaign": config.get("campaign"),
        "sequence_tree": resolve_sequence_tree(config, sample_messages=sample_messages),
        "sequence_steps": config.get("sequence_steps"),
    }
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote HeyReach sequence JSON to %s", destination)
    return destination


def run_heyreach_ohcq_sequence_build(
    *,
    config_path: Path | None = None,
    enriched_path: Path | None = None,
    flags_path: Path | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    config = load_heyreach_config(config_path)
    rows = read_clay_enriched_leads(enriched_path=enriched_path, flags_path=flags_path, config=config)
    if limit is not None:
        rows = rows[: max(0, int(limit))]

    leads = build_heyreach_don_leads(rows, config=config)
    sample_messages = render_messages_for_lead(rows[0], config=config) if rows else {}
    import_csv = write_heyreach_import_csv(leads, config=config)
    sequence_json = write_sequence_json(config, sample_messages=sample_messages)

    live_ready = sum(1 for lead in leads if lead.don_linkedin_url)
    return {
        "ok": True,
        "dry_run": dry_run,
        "input_rows": len(rows),
        "heyreach_leads": len(leads),
        "live_send_ready": live_ready,
        "import_csv": str(import_csv),
        "sequence_json": str(sequence_json),
        "sample_lead": leads[0].to_import_row() if leads else {},
        "sample_county_phrase": leads[0].county_phrase if leads else "",
        "channels": ["linkedin_connection_request", "linkedin_message", "email_follow_up"],
    }
