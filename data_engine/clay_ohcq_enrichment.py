"""Clay.com integration — OHCQ staffing citation CSV → enrichment payloads."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from data_engine.md_county_normalizer import normalize_md_county
from data_engine.paths import LEADS_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = REPO_ROOT / "integrations" / "clay" / "ohcq_citation_enrichment.template.json"
DEFAULT_INPUT_CSV = LEADS_DIR / "ohcq_staffing_citation_flags_md.csv"


@dataclass(frozen=True)
class ClayOhcqLeadRow:
    facility_name: str
    county: str
    facility_type: str
    flag_reason: str
    deficiency_summary: str
    md_license_number: str
    cms_ccn: str
    search_location: str
    record_id: str

    def to_webhook_row(self) -> dict[str, str]:
        return {
            "Facility Name": self.facility_name,
            "Maryland County": self.county,
            "Facility Type": self.facility_type,
            "Staffing Flag Reason": self.flag_reason,
            "Citation Summary": self.deficiency_summary,
            "MD License Number": self.md_license_number,
            "CMS CCN": self.cms_ccn,
            "Search Location": self.search_location,
            "VettedMe Record ID": self.record_id,
        }

    def to_clay_cells(self, field_map: dict[str, str]) -> dict[str, str]:
        webhook = self.to_webhook_row()
        cells: dict[str, str] = {}
        for logical_key, field_id in field_map.items():
            clay_column = _CLAY_COLUMN_BY_LOGICAL.get(logical_key)
            if not clay_column:
                continue
            value = webhook.get(clay_column, "")
            if field_id and value:
                cells[field_id] = value
        return cells


_CLAY_COLUMN_BY_LOGICAL = {
    "facility_name": "Facility Name",
    "county": "Maryland County",
    "facility_type": "Facility Type",
    "flag_reason": "Staffing Flag Reason",
    "deficiency_summary": "Citation Summary",
    "md_license_number": "MD License Number",
    "search_location": "Search Location",
}


def load_clay_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("clay_config_must_be_object")
    return payload


def _slugify(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return token[:48] or "facility"


def _record_id(facility_name: str, county: str) -> str:
    return f"ohcq-{_slugify(facility_name)}-{_slugify(county)}"


def _search_location(county: str) -> str:
    county_token = str(county or "").strip()
    if county_token.lower().endswith("county"):
        return f"{county_token}, Maryland, United States"
    if county_token.lower() == "baltimore city":
        return "Baltimore City, Maryland, United States"
    return f"{county_token} County, Maryland, United States"


def read_ohcq_citation_csv(
    csv_path: Path | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> list[ClayOhcqLeadRow]:
    cfg = config or load_clay_config()
    input_cfg = cfg.get("input") or {}
    relative = str(input_cfg.get("path") or DEFAULT_INPUT_CSV.relative_to(REPO_ROOT))
    source = csv_path or (REPO_ROOT / relative)
    if not source.exists():
        raise FileNotFoundError(f"ohcq_citation_csv_missing:{source}")

    dedupe_keys = tuple(input_cfg.get("dedupe_keys") or ("facility_name", "county"))
    seen: set[tuple[str, str]] = set()
    rows: list[ClayOhcqLeadRow] = []

    with source.open(newline="", encoding=str(input_cfg.get("encoding") or "utf-8")) as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            facility_name = str(raw.get("facility_name") or "").strip()
            county_result = normalize_md_county(str(raw.get("county") or ""))
            county = county_result.normalized
            if not facility_name or not county:
                continue
            dedupe_key = (
                _slugify(facility_name) if "facility_name" in dedupe_keys else facility_name.lower(),
                _slugify(county) if "county" in dedupe_keys else county.lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                ClayOhcqLeadRow(
                    facility_name=facility_name,
                    county=county,
                    facility_type=str(raw.get("facility_type") or "").strip(),
                    flag_reason=str(raw.get("flag_reason") or "").strip(),
                    deficiency_summary=str(raw.get("deficiency_summary") or "").strip(),
                    md_license_number=str(raw.get("md_license_number") or "").strip(),
                    cms_ccn=str(raw.get("cms_ccn") or "").strip(),
                    search_location=_search_location(county),
                    record_id=_record_id(facility_name, county),
                )
            )
    return rows


def resolve_field_id_map(config: dict[str, Any]) -> dict[str, str]:
    mappings = config.get("input_column_mappings") or {}
    resolved: dict[str, str] = {}
    for logical_key, spec in mappings.items():
        if not isinstance(spec, dict):
            continue
        env_name = str(spec.get("clay_field_id_env") or "").strip()
        if not env_name:
            continue
        field_id = str(os.environ.get(env_name) or "").strip()
        if field_id:
            resolved[logical_key] = field_id
    return resolved


def build_webhook_payload(rows: list[ClayOhcqLeadRow]) -> list[dict[str, str]]:
    return [row.to_webhook_row() for row in rows]


def build_v3_records_payload(
    rows: list[ClayOhcqLeadRow],
    *,
    field_map: dict[str, str],
) -> dict[str, Any]:
    records = []
    for row in rows:
        cells = row.to_clay_cells(field_map)
        if not cells:
            cells = row.to_webhook_row()
        records.append({"id": row.record_id, "cells": cells})
    return {"records": records}


def push_rows_to_clay_webhook(
    rows: list[ClayOhcqLeadRow],
    *,
    webhook_url: str,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not webhook_url.strip():
        raise ValueError("CLAY_TABLE_WEBHOOK_URL is required for webhook push")

    payload_rows = build_webhook_payload(rows)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "mode": "webhook",
            "row_count": len(payload_rows),
            "sample": payload_rows[:2],
        }

    owns_client = client is None
    http = client or httpx.Client(timeout=60.0)
    pushed = 0
    try:
        for row_payload in payload_rows:
            response = http.post(webhook_url, json=row_payload)
            response.raise_for_status()
            pushed += 1
    finally:
        if owns_client:
            http.close()

    return {"ok": True, "dry_run": False, "mode": "webhook", "row_count": pushed}


def push_rows_to_clay_v3(
    rows: list[ClayOhcqLeadRow],
    *,
    table_id: str,
    session_cookie: str,
    field_map: dict[str, str],
    batch_size: int = 50,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not table_id.strip():
        raise ValueError("CLAY_TABLE_ID is required for v3 push")
    if not session_cookie.strip():
        raise ValueError("CLAY_SESSION_COOKIE is required for v3 push")

    batches = [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]
    if dry_run:
        sample = build_v3_records_payload(rows[: min(2, len(rows))], field_map=field_map)
        return {
            "ok": True,
            "dry_run": True,
            "mode": "v3",
            "row_count": len(rows),
            "batch_count": len(batches),
            "sample": sample,
        }

    owns_client = client is None
    http = client or httpx.Client(
        timeout=90.0,
        headers={"Content-Type": "application/json", "Cookie": session_cookie},
    )
    pushed = 0
    try:
        for batch in batches:
            body = build_v3_records_payload(batch, field_map=field_map)
            response = http.post(f"https://api.clay.com/v3/tables/{table_id}/records", json=body)
            response.raise_for_status()
            pushed += len(batch)
    finally:
        if owns_client:
            http.close()

    return {"ok": True, "dry_run": False, "mode": "v3", "row_count": pushed, "batch_count": len(batches)}


def run_clay_ohcq_enrichment_push(
    *,
    csv_path: Path | None = None,
    config_path: Path | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    config = load_clay_config(config_path)
    rows = read_ohcq_citation_csv(csv_path, config=config)
    if limit is not None:
        rows = rows[: max(0, int(limit))]

    webhook_url = str(os.environ.get("CLAY_TABLE_WEBHOOK_URL") or "").strip()
    table_id = str(os.environ.get("CLAY_TABLE_ID") or "").strip()
    session_cookie = str(os.environ.get("CLAY_SESSION_COOKIE") or "").strip()
    field_map = resolve_field_id_map(config)
    batch_size = int((config.get("clay_table") or {}).get("batch_size") or 50)

    if webhook_url:
        push_result = push_rows_to_clay_webhook(rows, webhook_url=webhook_url, dry_run=dry_run)
    elif table_id and session_cookie:
        push_result = push_rows_to_clay_v3(
            rows,
            table_id=table_id,
            session_cookie=session_cookie,
            field_map=field_map,
            batch_size=batch_size,
            dry_run=dry_run,
        )
    elif dry_run:
        push_result = {
            "ok": True,
            "dry_run": True,
            "mode": "preview",
            "row_count": len(rows),
            "sample": build_webhook_payload(rows[:2]),
        }
    else:
        raise ValueError(
            "Configure CLAY_TABLE_WEBHOOK_URL or CLAY_TABLE_ID + CLAY_SESSION_COOKIE + field IDs"
        )

    return {
        "ok": True,
        "input_rows": len(rows),
        "config_template": str(config_path or DEFAULT_CONFIG_PATH),
        "target_roles": [role.get("display_name") for role in config.get("target_roles") or []],
        "push": push_result,
    }


def write_staging_enriched_csv(
    rows: list[ClayOhcqLeadRow],
    *,
    config: dict[str, Any] | None = None,
    output_path: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Write Clay-shaped CSV with empty enrichment columns for offline pipeline testing."""
    cfg = config or load_clay_config()
    export_cfg = cfg.get("export") or {}
    default_name = "ohcq_staffing_citation_enriched_staging_md.csv"
    relative = str(export_cfg.get("path") or DEFAULT_INPUT_CSV.relative_to(REPO_ROOT))
    if output_path is None:
        if relative.endswith("_md.csv"):
            staging_name = relative.replace("_md.csv", "_staging_md.csv")
        else:
            staging_name = default_name
        destination = LEADS_DIR / Path(staging_name).name
    else:
        destination = output_path

    if destination.exists() and not overwrite:
        logger.info("Staging enriched CSV already exists at %s — skipping rewrite", destination)
        return destination

    columns = list(export_cfg.get("columns") or [])
    if not columns:
        columns = [
            "facility_name",
            "county",
            "facility_type",
            "flag_reason",
            "don_full_name",
            "don_verified_email",
            "don_direct_phone",
            "don_linkedin_url",
        ]

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            payload = {
                "facility_name": row.facility_name,
                "county": row.county,
                "facility_type": row.facility_type,
                "flag_reason": row.flag_reason,
                "don_full_name": "",
                "don_verified_email": "",
                "don_direct_phone": "",
                "don_linkedin_url": "",
                "hr_staffing_coordinator_full_name": "",
                "hr_staffing_coordinator_verified_email": "",
                "hr_staffing_coordinator_direct_phone": "",
                "hr_staffing_coordinator_linkedin_url": "",
                "clay_record_id": row.record_id,
                "enriched_at_utc": "",
            }
            writer.writerow({col: payload.get(col, "") for col in columns})
    logger.info("Wrote %s staging enriched rows to %s", len(rows), destination)
    return destination
