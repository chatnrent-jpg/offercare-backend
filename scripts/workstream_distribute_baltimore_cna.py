"""CLI — distribute Baltimore instant-pay CNA job posts via Workstream API."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.workstream_job_bridge import run_workstream_baltimore_cna_distribution

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Workstream Baltimore CNA job distribution bridge")
    parser.add_argument("--dry-run", action="store_true", help="Preview payloads without live Workstream push")
    parser.add_argument("--live", action="store_true", help="Force live push (requires WORKSTREAM credentials)")
    args = parser.parse_args()

    dry_run = True
    if args.live:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    summary = run_workstream_baltimore_cna_distribution(dry_run=dry_run)
    print(json.dumps(summary, indent=2))
    channels = summary.get("channels") or []
    print(f"Workstream bridge complete — channels: {', '.join(channels)} -> {summary.get('export_json')}")
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
