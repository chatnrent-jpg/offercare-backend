"""Shift Sniper Matrix — matching priority and placement decay math."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

EliminationReason = Literal["non_compliant", "rate_below_minimum"]


@dataclass(frozen=True)
class SniperWeights:
    compliance: float = 100.0
    rate_delta: float = 10.0
    response_propensity: float = 25.0
    fatigue: float = 5.0


@dataclass(frozen=True)
class ClinicianCandidate:
    clinician_id: str
    compliance: int
    min_rate: float
    response_propensity: float
    fatigue: float = 0.0


@dataclass(frozen=True)
class RankedClinician:
    clinician_id: str
    priority_score: float
    rate_delta: float
    rank: int


@dataclass(frozen=True)
class EliminatedClinician:
    clinician_id: str
    reason: EliminationReason
    rate_delta: float


def rate_delta(*, shift_pay: float, min_rate: float) -> float:
    return float(shift_pay) - float(min_rate)


def matching_priority_score(
    *,
    shift_pay: float,
    candidate: ClinicianCandidate,
    weights: SniperWeights | None = None,
) -> float | None:
    """P_{i,j} = w1*C_j + w2*R_{i,j} + w3*H_j - w4*T_j. None = eliminated."""
    w = weights or SniperWeights()
    compliance = int(candidate.compliance)
    if compliance != 1:
        return None

    delta = rate_delta(shift_pay=shift_pay, min_rate=candidate.min_rate)
    if delta < 0:
        return None

    return (
        w.compliance * compliance
        + w.rate_delta * delta
        + w.response_propensity * float(candidate.response_propensity)
        - w.fatigue * float(candidate.fatigue)
    )


def placement_probability(
    elapsed_minutes: float,
    *,
    p_max: float = 0.95,
    decay_lambda: float = 0.35,
) -> float:
    """Pr(t) = P_max * e^(-lambda * t)."""
    t = max(float(elapsed_minutes), 0.0)
    return float(p_max) * math.exp(-float(decay_lambda) * t)


def rank_clinicians_for_shift(
    *,
    shift_pay: float,
    candidates: list[ClinicianCandidate],
    weights: SniperWeights | None = None,
) -> tuple[list[RankedClinician], list[EliminatedClinician]]:
    ranked_rows: list[tuple[str, float, float]] = []
    eliminated: list[EliminatedClinician] = []

    for candidate in candidates:
        delta = rate_delta(shift_pay=shift_pay, min_rate=candidate.min_rate)
        if int(candidate.compliance) != 1:
            eliminated.append(
                EliminatedClinician(
                    clinician_id=candidate.clinician_id,
                    reason="non_compliant",
                    rate_delta=delta,
                )
            )
            continue
        if delta < 0:
            eliminated.append(
                EliminatedClinician(
                    clinician_id=candidate.clinician_id,
                    reason="rate_below_minimum",
                    rate_delta=delta,
                )
            )
            continue

        score = matching_priority_score(
            shift_pay=shift_pay,
            candidate=candidate,
            weights=weights,
        )
        if score is None:
            continue
        ranked_rows.append((candidate.clinician_id, score, delta))

    ranked_rows.sort(key=lambda row: row[1], reverse=True)
    ranked = [
        RankedClinician(
            clinician_id=clinician_id,
            priority_score=round(score, 4),
            rate_delta=round(delta, 4),
            rank=index,
        )
        for index, (clinician_id, score, delta) in enumerate(ranked_rows, start=1)
    ]
    return ranked, eliminated


def saint_judes_icu_demo(
    weights: SniperWeights | None = None,
) -> dict[str, object]:
    """Saint Jude's ICU $120/hr example from the OfferCare blueprint."""
    shift_pay = 120.0
    candidates = [
        ClinicianCandidate("nurse_a", 1, 85.0, 0.85, 0.0),
        ClinicianCandidate("nurse_b", 1, 110.0, 0.95, 1.0),
        ClinicianCandidate("nurse_c", 1, 130.0, 0.80, 0.0),
    ]
    ranked, eliminated = rank_clinicians_for_shift(
        shift_pay=shift_pay,
        candidates=candidates,
        weights=weights,
    )
    return {
        "facility": "Saint Jude's ICU",
        "shift_pay": shift_pay,
        "notify_order": [row.clinician_id for row in ranked],
        "ranked": [
            {
                "clinician_id": row.clinician_id,
                "rank": row.rank,
                "priority_score": row.priority_score,
                "rate_delta": row.rate_delta,
            }
            for row in ranked
        ],
        "eliminated": [
            {
                "clinician_id": row.clinician_id,
                "reason": row.reason,
                "rate_delta": row.rate_delta,
            }
            for row in eliminated
        ],
        "fill_probability_90s": round(placement_probability(1.5), 4),
    }
