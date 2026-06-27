"""Post-shift timesheet reconciliation — staging desk (no live invoicing)."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIFTS_PATH = REPO_ROOT / "logs" / "manus" / "active_shifts.json"
PROVIDERS_PATH = REPO_ROOT / "logs" / "manus" / "processed_providers.json"
OUTPUT_PATH = REPO_ROOT / "logs" / "manus" / "reconciled_timesheets.json"

COMAR_MAX_SINGLE_SHIFT_HOURS = 12
WEEKLY_OT_THRESHOLD_HOURS = 40
OT_MULTIPLIER = 1.5

BILL_RATES = {"CNA": 45.0, "LPN": 65.0}
PAY_RATES = {"CNA": 30.0, "LPN": 45.0}

SCHEDULED_HOURS_STANDARD = 8


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _find_eligible_provider(applicants: list[dict[str, Any]], required_role: str) -> dict[str, Any]:
    role = str(required_role or "").upper()
    for applicant in applicants:
        if not bool(applicant.get("placement_eligible")):
            continue
        if str(applicant.get("license_type") or "").upper() == role:
            return applicant
    raise ValueError(f"no placement-eligible provider found for role {role}")


def _rates_for_role(role: str) -> tuple[float, float]:
    token = str(role or "").upper()
    if token not in BILL_RATES:
        raise ValueError(f"unsupported role for rate card: {token}")
    return BILL_RATES[token], PAY_RATES[token]


def _build_mock_timesheets(shifts: list[dict[str, Any]], applicants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(shifts) < 2:
        raise ValueError("need at least 2 active shifts for mock timesheet pairing")

    shift_one = shifts[0]
    shift_two = shifts[1]
    provider_one = _find_eligible_provider(applicants, str(shift_one["required_role"]))
    provider_two = _find_eligible_provider(applicants, str(shift_two["required_role"]))

    return [
        {
            "timesheet_id": str(uuid.uuid4()),
            "order_id": shift_one["order_id"],
            "facility_name": shift_one["facility_name"],
            "facility_type": shift_one["facility_type"],
            "county": shift_one["county"],
            "provider_name": provider_one["name"],
            "provider_license_number": provider_one["license_number"],
            "role": str(shift_one["required_role"]).upper(),
            "scheduled_hours": SCHEDULED_HOURS_STANDARD,
            "hours_worked": float(SCHEDULED_HOURS_STANDARD),
            "shift_timestamp": shift_one["shift_timestamp"],
        },
        {
            "timesheet_id": str(uuid.uuid4()),
            "order_id": shift_two["order_id"],
            "facility_name": shift_two["facility_name"],
            "facility_type": shift_two["facility_type"],
            "county": shift_two["county"],
            "provider_name": provider_two["name"],
            "provider_license_number": provider_two["license_number"],
            "role": str(shift_two["required_role"]).upper(),
            "scheduled_hours": SCHEDULED_HOURS_STANDARD,
            "hours_worked": 14.0,
            "shift_timestamp": shift_two["shift_timestamp"],
        },
    ]


def reconcile_timesheet(
    timesheet: dict[str, Any],
    *,
    weekly_hours_prior: float = 0.0,
) -> dict[str, Any]:
    role = str(timesheet["role"]).upper()
    bill_rate, pay_rate = _rates_for_role(role)
    hours_worked = float(timesheet["hours_worked"])

    gross_bill_amount = round(hours_worked * bill_rate, 2)

    surge_hours = max(0.0, hours_worked - COMAR_MAX_SINGLE_SHIFT_HOURS)
    weekly_hours_total = weekly_hours_prior + hours_worked
    weekly_ot_hours = max(0.0, weekly_hours_total - WEEKLY_OT_THRESHOLD_HOURS)

    regular_hours = min(hours_worked, COMAR_MAX_SINGLE_SHIFT_HOURS)
    gross_pay_amount = round(regular_hours * pay_rate, 2)

    overtime_penalty = 0.0
    overtime_hours = 0.0
    if surge_hours > 0:
        overtime_hours = surge_hours
        overtime_penalty = round(surge_hours * pay_rate * OT_MULTIPLIER, 2)
        gross_pay_amount = round(regular_hours * pay_rate + overtime_penalty, 2)
    elif weekly_ot_hours > 0:
        overtime_hours = weekly_ot_hours
        overtime_penalty = round(weekly_ot_hours * pay_rate * OT_MULTIPLIER, 2)
        gross_pay_amount = round(hours_worked * pay_rate + overtime_penalty, 2)

    desk_margin = round(gross_bill_amount - gross_pay_amount, 2)

    compliance_hold = hours_worked > COMAR_MAX_SINGLE_SHIFT_HOURS
    if compliance_hold:
        status = "OVERTIME_COMPLIANCE_HOLD"
        invoice_generation_halted = True
    else:
        status = "RECONCILED"
        invoice_generation_halted = False

    return {
        **timesheet,
        "bill_rate": bill_rate,
        "pay_rate": pay_rate,
        "gross_bill_amount": gross_bill_amount,
        "gross_pay_amount": gross_pay_amount,
        "desk_margin": desk_margin,
        "overtime_hours": overtime_hours,
        "overtime_penalty": overtime_penalty,
        "comar_max_single_shift_hours": COMAR_MAX_SINGLE_SHIFT_HOURS,
        "status": status,
        "invoice_generation_halted": invoice_generation_halted,
        "reconciled_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def process_timesheets() -> dict[str, Any]:
    shifts_payload = _load_json(SHIFTS_PATH)
    providers_payload = _load_json(PROVIDERS_PATH)

    shifts = shifts_payload.get("shifts") or []
    applicants = providers_payload.get("applicants") or []
    mock_timesheets = _build_mock_timesheets(shifts, applicants)

    reconciled: list[dict[str, Any]] = []
    weekly_hours_running = 0.0
    for timesheet in mock_timesheets:
        record = reconcile_timesheet(timesheet, weekly_hours_prior=weekly_hours_running)
        weekly_hours_running += float(timesheet["hours_worked"])
        reconciled.append(record)

    holds = sum(1 for row in reconciled if row["status"] == "OVERTIME_COMPLIANCE_HOLD")

    return {
        "mode": "STAGING",
        "live_execution": False,
        "product": "VettedCare.ai Timesheet Reconciliation Desk",
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "timesheet_count": len(reconciled),
        "overtime_compliance_holds": holds,
        "rate_card": {
            "bill_rates": BILL_RATES,
            "pay_rates": PAY_RATES,
        },
        "comar_guardrails": {
            "max_single_shift_hours": COMAR_MAX_SINGLE_SHIFT_HOURS,
            "weekly_overtime_threshold_hours": WEEKLY_OT_THRESHOLD_HOURS,
            "overtime_multiplier": OT_MULTIPLIER,
        },
        "timesheets": reconciled,
    }


def write_output(payload: dict[str, Any], path: Path = OUTPUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def main() -> int:
    try:
        result = process_timesheets()
        out_path = write_output(result)
        print(f"STAGING — reconciled {result['timesheet_count']} timesheet(s)")
        print(f"Overtime compliance holds: {result['overtime_compliance_holds']}")
        for row in result["timesheets"]:
            print(
                f"  {row['provider_name']} | {row['role']} | {row['hours_worked']}h | "
                f"bill=${row['gross_bill_amount']:.2f} pay=${row['gross_pay_amount']:.2f} "
                f"margin=${row['desk_margin']:.2f} | {row['status']}"
            )
        print(f"Output: {out_path}")
        return 0
    except Exception as exc:
        print(f"FATAL — timesheet reconciliation aborted: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
