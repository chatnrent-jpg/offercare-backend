"""Run Maryland ops desk orchestrator — Manus-callable staging pipeline."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy.desk_orchestrator import DeskOrchestrator, build_manus_desk_manifest

PROVIDERS_PATH = REPO_ROOT / "logs" / "manus" / "processed_providers.json"
SHIFTS_PATH = REPO_ROOT / "logs" / "manus" / "active_shifts.json"
TIMESHEETS_PATH = REPO_ROOT / "logs" / "manus" / "reconciled_timesheets.json"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing staging file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    providers = _load_json(PROVIDERS_PATH)
    shifts_payload = _load_json(SHIFTS_PATH)
    timesheets = _load_json(TIMESHEETS_PATH)

    shifts = shifts_payload.get("shifts") or []
    if not shifts:
        raise SystemExit("No shifts in active_shifts.json")

    target_shift = shifts[0]
    evaluation_ts = datetime.now(timezone.utc).isoformat()

    orchestrator = DeskOrchestrator(
        providers,
        timesheets_payload=timesheets,
    )

    booking_run = orchestrator.run_full_desk_cycle(
        target_shift,
        evaluation_timestamp=evaluation_ts,
    )
    log_path = DeskOrchestrator.persist_run(booking_run)

    callout_run = orchestrator.run_callout_pipeline(
        disrupted_shift_id=str(target_shift.get("order_id")),
        original_provider_id="CNA-MD-88421",
    )
    callout_run["run_id"] = f"callout-{evaluation_ts}"
    callout_run["staged_at_utc"] = evaluation_ts
    callout_run["live_execution"] = False
    DeskOrchestrator.persist_run(callout_run, log_path)

    penalty_run = orchestrator.run_penalty_pipeline(
        facility_id="MD-SNF-ARBOR-RIDGE",
        provider_id="CNA-MD-88421",
        total_hours_worked=45.0,
    )
    penalty_run["run_id"] = f"penalty-{evaluation_ts}"
    penalty_run["staged_at_utc"] = evaluation_ts
    penalty_run["live_execution"] = False
    DeskOrchestrator.persist_run(penalty_run, log_path)

    handoff_path = DeskOrchestrator.write_manus_handoff(build_manus_desk_manifest(REPO_ROOT))

    print("Desk pipeline complete (STAGING).")
    print(f"  shift: {target_shift.get('facility_name')} · {target_shift.get('required_role')}")
    print(f"  booking status: {booking_run['booking']['status']}")
    print(f"  surge rate: ${booking_run['booking']['surge_pricing']['final_surge_bill_rate']}/hr")
    print(f"  callout status: {callout_run['status']}")
    print(f"  penalty fee: ${penalty_run['audit']['calculated_penalty_fee']}")
    print(f"  log: {log_path.relative_to(REPO_ROOT)}")
    print(f"  manus handoff: {handoff_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
