"""Surge pricing engine — isolated dynamic facility bill-rate math (staging)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SHORT_NOTICE_HOURS = 4
SHORT_NOTICE_MULTIPLIER = 1.25
NIGHT_SHIFT_MULTIPLIER = 1.15
MAX_SURGE_MULTIPLIER = 1.4

DEFAULT_BASE_BILL_RATES: dict[str, float] = {
    "CNA": 45.0,
    "LPN": 65.0,
}


def _parse_timestamp(value: str) -> datetime:
    token = str(value or "").strip()
    if not token:
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_role(value: str) -> str:
    return str(value or "").strip().upper()


def _shift_start_timestamp(shift_request: dict[str, Any]) -> str:
    for key in ("start_time", "shift_timestamp", "shift_start"):
        raw = shift_request.get(key)
        if raw:
            return str(raw)
    raise ValueError("shift_request must include start_time or shift_timestamp")


def _is_night_shift_window(shift_start: datetime) -> bool:
    hour = shift_start.hour
    return hour >= 23 or hour < 7


class SurgePricingEngine:
    """Calculates compounded surge multipliers on standard facility bill rates."""

    def __init__(self, base_bill_rates: dict[str, float] | None = None) -> None:
        rates = dict(base_bill_rates or DEFAULT_BASE_BILL_RATES)
        if not rates:
            raise ValueError("base_bill_rates must not be empty")
        self.base_bill_rates = { _normalize_role(role): float(rate) for role, rate in rates.items() }

    def _resolve_base_rate(self, shift_request: dict[str, Any]) -> float:
        role = _normalize_role(str(shift_request.get("required_role") or ""))
        if not role:
            raise ValueError("shift_request must include required_role")
        if role not in self.base_bill_rates:
            raise ValueError(f"unsupported required_role for billing: {role}")
        return float(self.base_bill_rates[role])

    def calculate_surge_rate(
        self,
        shift_request: dict[str, Any],
        request_timestamp: str,
    ) -> dict[str, Any]:
        if not isinstance(shift_request, dict):
            raise TypeError("shift_request must be a dict")

        request_ts = _parse_timestamp(request_timestamp)
        shift_start = _parse_timestamp(_shift_start_timestamp(shift_request))
        base_bill_rate = self._resolve_base_rate(shift_request)

        hours_until_shift = (shift_start - request_ts).total_seconds() / 3600.0
        if hours_until_shift < 0:
            raise ValueError("request_timestamp must be on or before shift start_time")

        triggered_tiers: list[str] = []
        multiplier = 1.0

        if hours_until_shift < SHORT_NOTICE_HOURS:
            triggered_tiers.append("SHORT_NOTICE_URGENCY")
            multiplier *= SHORT_NOTICE_MULTIPLIER

        if _is_night_shift_window(shift_start):
            triggered_tiers.append("NIGHT_SHIFT_DIFFERENTIAL")
            multiplier *= NIGHT_SHIFT_MULTIPLIER

        raw_multiplier = multiplier
        applied_multiplier = min(multiplier, MAX_SURGE_MULTIPLIER)
        capped = raw_multiplier > MAX_SURGE_MULTIPLIER

        if not triggered_tiers:
            surge_tier_trigger = "STANDARD"
        elif capped:
            surge_tier_trigger = "+".join(triggered_tiers) + "_CAPPED"
        else:
            surge_tier_trigger = "+".join(triggered_tiers)

        final_surge_bill_rate = round(base_bill_rate * applied_multiplier, 2)

        return {
            "base_bill_rate": base_bill_rate,
            "applied_multiplier": round(applied_multiplier, 4),
            "final_surge_bill_rate": final_surge_bill_rate,
            "surge_tier_trigger": surge_tier_trigger,
            "raw_compounded_multiplier": round(raw_multiplier, 4),
            "capped_at_max": capped,
            "hours_until_shift": round(hours_until_shift, 2),
        }


if __name__ == "__main__":
    engine = SurgePricingEngine()

    # Standard day shift with ample lead time — no surge.
    standard_shift = {
        "order_id": "standard-day-cna",
        "required_role": "CNA",
        "shift_timestamp": "2026-06-27T14:00:00+00:00",
    }
    result = engine.calculate_surge_rate(standard_shift, "2026-06-26T10:00:00+00:00")
    assert result["base_bill_rate"] == 45.0
    assert result["applied_multiplier"] == 1.0
    assert result["final_surge_bill_rate"] == 45.0
    assert result["surge_tier_trigger"] == "STANDARD"

    # Short-notice only (< 4h) — 1.25x.
    urgent_shift = {
        "required_role": "LPN",
        "shift_timestamp": "2026-06-27T12:00:00+00:00",
    }
    result = engine.calculate_surge_rate(urgent_shift, "2026-06-27T09:30:00+00:00")
    assert result["base_bill_rate"] == 65.0
    assert result["applied_multiplier"] == 1.25
    assert result["final_surge_bill_rate"] == 81.25
    assert result["surge_tier_trigger"] == "SHORT_NOTICE_URGENCY"

    # Night differential only — 1.15x.
    night_shift = {
        "required_role": "CNA",
        "shift_timestamp": "2026-06-28T02:00:00+00:00",
    }
    result = engine.calculate_surge_rate(night_shift, "2026-06-27T10:00:00+00:00")
    assert result["applied_multiplier"] == 1.15
    assert result["final_surge_bill_rate"] == 51.75
    assert result["surge_tier_trigger"] == "NIGHT_SHIFT_DIFFERENTIAL"

    # Short-notice night shift — compound 1.25 * 1.15 = 1.4375, capped at 1.4x.
    compound_shift = {
        "order_id": "eb1ac566-night-callout",
        "facility_name": "Arbor Ridge at Riderwood",
        "required_role": "CNA",
        "shift_timestamp": "2026-06-28T02:00:00+00:00",
    }
    result = engine.calculate_surge_rate(compound_shift, "2026-06-27T22:30:00+00:00")
    assert result["base_bill_rate"] == 45.0
    assert result["raw_compounded_multiplier"] == 1.4375
    assert result["applied_multiplier"] == 1.4
    assert result["final_surge_bill_rate"] == 63.0
    assert result["surge_tier_trigger"] == "SHORT_NOTICE_URGENCY+NIGHT_SHIFT_DIFFERENTIAL_CAPPED"
    assert result["capped_at_max"] is True
    assert result["hours_until_shift"] == 3.5

    print("SurgePricingEngine self-test passed.")
    print("  standard day shift -> 1.0x ($45.00/hr CNA)")
    print("  short-notice LPN -> 1.25x ($81.25/hr)")
    print("  night CNA -> 1.15x ($51.75/hr)")
    print("  short-notice night CNA -> capped 1.4x ($63.00/hr)")
