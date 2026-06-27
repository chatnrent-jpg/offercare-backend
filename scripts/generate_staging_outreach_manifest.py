"""Generate staging B2B outreach manifest for Manus (no live send)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.database import SessionLocal
from data_engine.md_staging_outreach_manifest import write_staging_outreach_manifest


def main() -> None:
    db = SessionLocal()
    try:
        path = write_staging_outreach_manifest(db)
        with path.open(encoding="utf-8") as handle:
            manifest = json.load(handle)
        print(json.dumps({"manifest_path": str(path), "summary": {
            "mode": manifest["mode"],
            "count": manifest["count"],
            "live_execution": manifest["live_execution"],
        }}, indent=2))
        print(json.dumps(manifest, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
