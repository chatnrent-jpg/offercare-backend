"""One-shot recruitment engine smoke test — sample CSV, contract, VMS JSON."""

from __future__ import annotations

import json
from pathlib import Path

from app.database import SessionLocal
from app.services.recruitment_dashboard import build_recruitment_dashboard, write_manus_recruitment_snapshot
from data_engine.contract_processor import process_incoming_contract
from data_engine.lead_schema import import_raw_leads_csv
from data_engine.paths import INCOMING_CONTRACTS_DIR, INCOMING_SHIFTS_DIR, RAW_LEADS_DIR
from data_engine.shift_ingest import ingest_shifts_from_directory

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    db = SessionLocal()
    try:
        lead_path = RAW_LEADS_DIR / "manus_test_leads.csv"
        contract_path = INCOMING_CONTRACTS_DIR / "manus_test_msa.txt"
        shift_path = INCOMING_SHIFTS_DIR / "manus_test_shifts.json"

        print("=== 1. Import B2B leads ===")
        print(json.dumps(import_raw_leads_csv(db, lead_path), indent=2))

        print("\n=== 2. Parse contract ===")
        print(json.dumps(process_incoming_contract(db, contract_path), indent=2))

        print("\n=== 3. Ingest VMS shifts ===")
        if shift_path.exists():
            print(json.dumps(ingest_shifts_from_directory(db), indent=2))
        else:
            print("shift file missing")

        print("\n=== 4. Dashboard summary ===")
        dash = build_recruitment_dashboard(db, limit=10)
        print(json.dumps(dash["summary"], indent=2))

        snap = write_manus_recruitment_snapshot(db)
        print(f"\n=== 5. Manus snapshot ===\n{snap}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
