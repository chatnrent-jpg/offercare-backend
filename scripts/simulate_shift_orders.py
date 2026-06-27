"""Simulate incoming open shift orders from Maryland facility registry (staging only)."""

from __future__ import annotations

import csv
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"
OUTPUT_PATH = REPO_ROOT / "logs" / "manus" / "active_shifts.json"

VALID_FACILITY_TYPES = frozenset({"SNF", "ALF"})
VALID_ROLES = ("CNA", "LPN")


def _normalize_facility_type(raw: str) -> str | None:
    token = str(raw or "").strip().upper()
    if token in VALID_FACILITY_TYPES:
        return token
    return None


def load_facility_profiles(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    profiles: list[dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            facility_name = str(row.get("facility_name") or "").strip()
            facility_type = _normalize_facility_type(str(row.get("facility_type") or ""))
            county = str(row.get("county") or "").strip()
            if not facility_name or not facility_type or not county:
                raise ValueError(f"row {row_number}: missing facility_name, facility_type, or county")
            profiles.append(
                {
                    "facility_name": facility_name,
                    "facility_type": facility_type,
                    "county": county,
                }
            )

    if not profiles:
        raise ValueError("no facility profiles found in CSV")
    return profiles


def generate_shift_orders(
    facilities: list[dict[str, str]],
    *,
    count: int = 3,
    seed: int = 42,
) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("count must be >= 1")
    if len(facilities) < count:
        raise ValueError(f"need at least {count} facilities, found {len(facilities)}")

    rng = random.Random(seed)
    sampled = rng.sample(facilities, count)
    base_date = datetime.now(timezone.utc).date()

    orders: list[dict[str, Any]] = []
    for index, facility in enumerate(sampled):
        shift_date = base_date + timedelta(days=index + 1)
        orders.append(
            {
                "order_id": str(uuid.uuid4()),
                "facility_name": facility["facility_name"],
                "facility_type": facility["facility_type"],
                "county": facility["county"],
                "required_role": VALID_ROLES[index % len(VALID_ROLES)],
                "shift_timestamp": f"{shift_date.isoformat()}T07:00:00+00:00",
            }
        )
    return orders


def write_active_shifts(orders: list[dict[str, Any]], path: Path = OUTPUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "STAGING",
        "live_execution": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product": "VettedCare.ai Active Shift Order Simulator",
        "count": len(orders),
        "shifts": orders,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def main() -> int:
    try:
        facilities = load_facility_profiles(CSV_PATH)
        orders = generate_shift_orders(facilities, count=3)
        out_path = write_active_shifts(orders)
        print(f"STAGING — generated {len(orders)} open shift order(s)")
        for order in orders:
            print(
                f"  {order['order_id'][:8]}… | {order['facility_name']} | "
                f"{order['facility_type']} | {order['required_role']} | {order['shift_timestamp']}"
            )
        print(f"Output: {out_path}")
        return 0
    except Exception as exc:
        print(f"FATAL — shift simulation aborted: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
