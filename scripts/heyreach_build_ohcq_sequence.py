#!/usr/bin/env python
"""Build HeyReach DON outreach CSV + sequence JSON from Clay-enriched OHCQ leads."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.heyreach_outreach import run_heyreach_ohcq_sequence_build


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import Clay-enriched OHCQ leads and build HeyReach LinkedIn + email "
            "sequence artifacts for Maryland Directors of Nursing."
        )
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--enriched-csv", type=Path, default=None)
    parser.add_argument("--flags-csv", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    summary = run_heyreach_ohcq_sequence_build(
        config_path=args.config,
        enriched_path=args.enriched_csv,
        flags_path=args.flags_csv,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"HeyReach sequence build complete — {summary['heyreach_leads']} leads "
            f"({summary['live_send_ready']} with LinkedIn URL) -> {summary['import_csv']}"
        )
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
