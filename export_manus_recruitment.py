#!/usr/bin/env python3
"""Export Manus recruitment snapshot for daily RFP/VMS briefing."""

from __future__ import annotations

from app.database import SessionLocal
from app.services.recruitment_dashboard import write_manus_recruitment_snapshot


def main() -> int:
    db = SessionLocal()
    try:
        path = write_manus_recruitment_snapshot(db)
    finally:
        db.close()
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
