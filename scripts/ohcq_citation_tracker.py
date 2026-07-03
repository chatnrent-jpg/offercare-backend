#!/usr/bin/env python
"""CLI — Maryland OHCQ staffing citation tracker for Manus / desk automation."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.ohcq_citation_tracker import DEFAULT_OUTPUT, run_ohcq_staffing_citation_sweep


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep Maryland MDH OHCQ portals and CMS nursing-home mirrors for "
            "insufficient staffing citations and below-mandate care hours."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write sample rows without live portal/API calls",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print run summary as JSON",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    summary = run_ohcq_staffing_citation_sweep(
        output_path=args.output,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"OHCQ staffing citation sweep complete — {summary['flag_count']} flagged facilities "
            f"-> {summary['output_csv']}"
        )
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
