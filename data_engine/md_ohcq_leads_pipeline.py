"""Offline Maryland OHCQ leads pipeline — tracker → Clay staging → HeyReach (no API keys required)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_engine.clay_ohcq_enrichment import (
    load_clay_config,
    read_ohcq_citation_csv,
    run_clay_ohcq_enrichment_push,
    write_staging_enriched_csv,
)
from data_engine.heyreach_outreach import run_heyreach_ohcq_sequence_build
from data_engine.md_county_normalizer import normalize_md_county
from data_engine.paths import LEADS_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

MANIFEST_PATH = REPO_ROOT / "logs" / "manus" / "md_ohcq_leads_pipeline_manifest.json"

INTEGRATION_KEYS = (
    ("CLAY_TABLE_WEBHOOK_URL", "Clay webhook push"),
    ("CLAY_TABLE_ID", "Clay v3 table push"),
    ("CLAY_SESSION_COOKIE", "Clay v3 session auth"),
    ("HEYREACH_API_KEY", "HeyReach API campaign control"),
    ("HEYREACH_LIST_ID", "HeyReach lead list import"),
    ("HEYREACH_CAMPAIGN_ID", "HeyReach campaign start"),
    ("HEYREACH_SENDER_ACCOUNT_IDS", "HeyReach LinkedIn sender accounts"),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def integration_keys_status() -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for env_name, purpose in INTEGRATION_KEYS:
        value = str(os.environ.get(env_name) or "").strip()
        status[env_name] = {
            "set": bool(value),
            "purpose": purpose,
            "assign_on": "keys day — add to .env before live push",
        }
    return status


def county_normalization_report(flags_path: Path) -> dict[str, Any]:
    import csv

    if not flags_path.exists():
        return {"total": 0, "verified": 0, "unverified": 0, "unverified_samples": []}

    verified = 0
    unverified_samples: list[str] = []
    total = 0
    with flags_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            total += 1
            result = normalize_md_county(str(row.get("county") or ""))
            if result.verified:
                verified += 1
            elif len(unverified_samples) < 15:
                unverified_samples.append(result.raw)

    return {
        "total": total,
        "verified": verified,
        "unverified": total - verified,
        "unverified_samples": unverified_samples,
    }


def run_md_ohcq_leads_pipeline(
    *,
    skip_tracker: bool = True,
    limit: int | None = None,
    dry_run: bool = False,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Build full offline pipeline artifacts; live API calls only when keys are present."""
    flags_csv = LEADS_DIR / "ohcq_staffing_citation_flags_md.csv"
    enriched_csv = LEADS_DIR / "ohcq_staffing_citation_enriched_md.csv"
    steps: list[dict[str, Any]] = []

    tracker_step: dict[str, Any] = {
        "step": "ohcq_citation_tracker",
        "status": "skipped",
        "note": "Use --run-tracker to refresh flags CSV from MDH/CMS portals",
    }
    if not skip_tracker:
        try:
            from data_engine.ohcq_citation_tracker import run_ohcq_citation_sweep

            tracker_result = run_ohcq_citation_sweep()
            tracker_step = {"step": "ohcq_citation_tracker", "status": "completed", **tracker_result}
        except Exception as exc:
            tracker_step = {"step": "ohcq_citation_tracker", "status": "failed", "error": str(exc)}
    elif not flags_csv.exists():
        tracker_step = {
            "step": "ohcq_citation_tracker",
            "status": "required",
            "error": f"Missing {flags_csv} — run scripts/run-ohcq-citation-tracker.bat first",
        }
    steps.append(tracker_step)

    clay_step: dict[str, Any] = {"step": "clay_enrichment", "status": "pending"}
    if flags_csv.exists():
        try:
            clay_config = load_clay_config()
            clay_rows = read_ohcq_citation_csv(flags_csv, config=clay_config)
            if limit is not None:
                clay_rows = clay_rows[: max(0, int(limit))]

            staging_path = write_staging_enriched_csv(clay_rows, config=clay_config, overwrite=False)
            push_preview = run_clay_ohcq_enrichment_push(
                csv_path=flags_csv,
                dry_run=True,
                limit=limit,
            )
            clay_step = {
                "step": "clay_enrichment",
                "status": "staging_ready",
                "input_rows": len(clay_rows),
                "staging_enriched_csv": str(staging_path),
                "live_enriched_csv": str(enriched_csv),
                "clay_push_preview": push_preview,
                "note": "Staging CSV has empty DON fields until Clay keys are assigned",
            }
        except Exception as exc:
            clay_step = {"step": "clay_enrichment", "status": "failed", "error": str(exc)}
    else:
        clay_step = {"step": "clay_enrichment", "status": "skipped", "error": "flags CSV missing"}
    steps.append(clay_step)

    heyreach_step: dict[str, Any] = {"step": "heyreach_sequence", "status": "pending"}
    if flags_csv.exists():
        try:
            heyreach_result = run_heyreach_ohcq_sequence_build(
                flags_path=flags_csv,
                enriched_path=enriched_csv if enriched_csv.exists() else None,
                limit=limit,
                dry_run=dry_run,
            )
            heyreach_step = {"step": "heyreach_sequence", "status": "completed", **heyreach_result}
        except Exception as exc:
            heyreach_step = {"step": "heyreach_sequence", "status": "failed", "error": str(exc)}
    else:
        heyreach_step = {"step": "heyreach_sequence", "status": "skipped", "error": "flags CSV missing"}
    steps.append(heyreach_step)

    keys = integration_keys_status()
    county_report = county_normalization_report(flags_csv)

    manifest = {
        "pipeline_id": "md-ohcq-leads-offline",
        "generated_at_utc": _utc_now_iso(),
        "mode": "offline_build",
        "live_execution": False,
        "manus_action": "REVIEW_ONLY — assign API keys on keys day before live Clay/HeyReach push",
        "artifacts": {
            "flags_csv": str(flags_csv),
            "staging_enriched_csv": str(LEADS_DIR / "ohcq_staffing_citation_enriched_staging_md.csv"),
            "live_enriched_csv": str(enriched_csv),
            "heyreach_import_csv": str(LEADS_DIR / "heyreach_md_don_ohcq_import.csv"),
            "heyreach_sequence_json": str(LEADS_DIR / "heyreach_md_don_ohcq_sequence.json"),
        },
        "integration_keys": keys,
        "keys_ready_for_live": all(
            keys[name]["set"]
            for name in ("CLAY_TABLE_WEBHOOK_URL", "HEYREACH_API_KEY", "HEYREACH_SENDER_ACCOUNT_IDS")
        ),
        "county_normalization": county_report,
        "steps": steps,
    }

    destination = manifest_path or MANIFEST_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote pipeline manifest to %s", destination)

    manifest["manifest_path"] = str(destination)
    manifest["ok"] = all(step.get("status") in {"completed", "staging_ready", "skipped"} for step in steps)
    return manifest
