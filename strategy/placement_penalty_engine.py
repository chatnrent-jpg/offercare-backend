"""Placement penalty engine — isolated contract vesting & buyout math (staging)."""

from __future__ import annotations

from typing import Any

DEFAULT_BUYOUT_FEE = 5000.0
DEFAULT_CONTRACT_MINIMUM_HOURS = 160
FULL_PENALTY_THRESHOLD_HOURS = 80
FULL_PENALTY_FEE = 5000.0
PRORATED_PENALTY_FEE = 2500.0


class PlacementPenaltyEngine:
    """Audits permanent-placement attempts against corporate vesting terms."""

    def __init__(
        self,
        *,
        standard_buyout_fee: float = DEFAULT_BUYOUT_FEE,
        contract_minimum_hours: int = DEFAULT_CONTRACT_MINIMUM_HOURS,
    ) -> None:
        if standard_buyout_fee < 0:
            raise ValueError("standard_buyout_fee must be non-negative")
        if contract_minimum_hours <= 0:
            raise ValueError("contract_minimum_hours must be positive")

        self.standard_buyout_fee = float(standard_buyout_fee)
        self.contract_minimum_hours = int(contract_minimum_hours)

    def _calculate_penalty_fee(self, total_hours_worked: float) -> float:
        if total_hours_worked >= self.contract_minimum_hours:
            return 0.0
        if total_hours_worked < FULL_PENALTY_THRESHOLD_HOURS:
            return FULL_PENALTY_FEE
        return PRORATED_PENALTY_FEE

    def audit_permanent_placement(
        self,
        facility_id: str,
        provider_id: str,
        total_hours_worked: float,
    ) -> dict[str, Any]:
        if not str(facility_id or "").strip():
            raise ValueError("facility_id is required")
        if not str(provider_id or "").strip():
            raise ValueError("provider_id is required")
        if total_hours_worked is None:
            raise TypeError("total_hours_worked is required")
        try:
            hours = float(total_hours_worked)
        except (TypeError, ValueError) as exc:
            raise TypeError("total_hours_worked must be numeric") from exc
        if hours < 0:
            raise ValueError("total_hours_worked must be non-negative")

        is_violation = hours < self.contract_minimum_hours
        penalty_fee = self._calculate_penalty_fee(hours)

        if not is_violation:
            invoice_status_flag = "FULLY_VESTED_CLEAR"
        elif penalty_fee >= FULL_PENALTY_FEE:
            invoice_status_flag = "MINIMUM_HOURS_VIOLATION_PENALTY"
        else:
            invoice_status_flag = "MINIMUM_HOURS_VIOLATION_PENALTY_PRORATED"

        return {
            "facility_id": str(facility_id).strip(),
            "provider_id": str(provider_id).strip(),
            "is_contract_violation": is_violation,
            "total_hours_recorded": round(hours, 2),
            "calculated_penalty_fee": round(penalty_fee, 2),
            "invoice_status_flag": invoice_status_flag,
            "contract_minimum_hours": self.contract_minimum_hours,
            "standard_buyout_fee": self.standard_buyout_fee,
        }


if __name__ == "__main__":
    engine = PlacementPenaltyEngine()

    # Facility poaches nurse at 45 hours — full $5,000 penalty.
    poach_audit = engine.audit_permanent_placement(
        facility_id="MD-SNF-ARBOR-RIDGE",
        provider_id="CNA-MD-88421",
        total_hours_worked=45.0,
    )
    assert poach_audit["is_contract_violation"] is True
    assert poach_audit["total_hours_recorded"] == 45.0
    assert poach_audit["calculated_penalty_fee"] == 5000.0
    assert poach_audit["invoice_status_flag"] == "MINIMUM_HOURS_VIOLATION_PENALTY"

    # Pro-rated band: 80–159 hours -> $2,500.
    mid_audit = engine.audit_permanent_placement(
        facility_id="MD-SNF-ADELPHI",
        provider_id="LPN-MD-55290",
        total_hours_worked=120.0,
    )
    assert mid_audit["is_contract_violation"] is True
    assert mid_audit["calculated_penalty_fee"] == 2500.0
    assert mid_audit["invoice_status_flag"] == "MINIMUM_HOURS_VIOLATION_PENALTY_PRORATED"

    # Fully vested at 160+ hours -> $0 buyout.
    vested_audit = engine.audit_permanent_placement(
        facility_id="MD-SNF-AUTUMN-LAKE",
        provider_id="CNA-MD-90331",
        total_hours_worked=160.0,
    )
    assert vested_audit["is_contract_violation"] is False
    assert vested_audit["calculated_penalty_fee"] == 0.0
    assert vested_audit["invoice_status_flag"] == "FULLY_VESTED_CLEAR"

    # Edge: exactly 80 hours triggers pro-rated tier (not full penalty).
    edge_audit = engine.audit_permanent_placement(
        facility_id="MD-SNF-EDGE",
        provider_id="CNA-MD-99001",
        total_hours_worked=80.0,
    )
    assert edge_audit["calculated_penalty_fee"] == 2500.0

    print("PlacementPenaltyEngine self-test passed.")
    print("  45h poach -> $5,000 · MINIMUM_HOURS_VIOLATION_PENALTY")
    print("  120h poach -> $2,500 · prorated violation")
    print("  160h vested -> $0 · FULLY_VESTED_CLEAR")
