"""CLI — offline Maryland OHCQ leads pipeline (no API keys required)."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from data_engine.md_ohcq_leads_pipeline import run_md_ohcq_leads_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MD OHCQ leads pipeline artifacts offline")
    parser.add_argument("--run-tracker", action="store_true", help="Refresh OHCQ citation flags from MDH/CMS")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for preview builds")
    parser.add_argument("--dry-run", action="store_true", help="No side effects beyond manifest + artifacts")
    args = parser.parse_args()

    summary = run_md_ohcq_leads_pipeline(
        skip_tracker=not args.run_tracker,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps({k: summary[k] for k in ("ok", "manifest_path", "integration_keys", "county_normalization") if k in summary}, indent=2))
    heyreach = next((s for s in summary.get("steps", []) if s.get("step") == "heyreach_sequence"), {})
    if heyreach.get("heyreach_leads"):
        print(
            f"HeyReach: {heyreach['heyreach_leads']} leads "
            f"({heyreach.get('live_send_ready', 0)} LinkedIn-ready)"
        )
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
