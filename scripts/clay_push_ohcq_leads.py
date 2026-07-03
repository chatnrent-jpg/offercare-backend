#!/usr/bin/env python
"""Push OHCQ staffing citation leads from /leads to Clay.com for DON + HR enrichment."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.clay_ohcq_enrichment import run_clay_ohcq_enrichment_push


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read leads/ohcq_staffing_citation_flags_md.csv and push rows to Clay.com "
            "for DON + HR Staffing Coordinator LinkedIn/email/phone enrichment."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Override OHCQ citation CSV path",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Clay integration config JSON (default: integrations/clay/ohcq_citation_enrichment.template.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build payloads without calling Clay")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to push")
    parser.add_argument("--json", action="store_true", help="Print summary JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    summary = run_clay_ohcq_enrichment_push(
        csv_path=args.csv,
        config_path=args.config,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        push = summary.get("push") or {}
        print(
            f"Clay OHCQ push complete — {summary.get('input_rows')} rows "
            f"via {push.get('mode')} (dry_run={push.get('dry_run')})"
        )
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
