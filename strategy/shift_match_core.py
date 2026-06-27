"""Shared shift-matching rules — staging JSON and PostgreSQL use the same core."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: str) -> datetime:
    token = str(value or "").strip()
    if not token:
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_facility_type(value: str) -> str:
    token = str(value or "").strip().upper()
    aliases = {
        "NURSING_HOME": "SNF",
        "SKILLED_NURSING": "SNF",
        "LONG_TERM_CARE": "SNF",
        "LTC": "SNF",
        "ASSISTED_LIVING": "ALF",
    }
    return aliases.get(token, token)


def effective_barrier(evaluation_timestamp: str, shift_request: dict[str, Any]) -> datetime:
    barrier = parse_timestamp(evaluation_timestamp)
    window_raw = shift_request.get("evaluation_window_barrier")
    if window_raw:
        window_barrier = parse_timestamp(str(window_raw))
        return min(barrier, window_barrier)
    return barrier


def verification_is_lookahead_safe(candidate: dict[str, Any], barrier: datetime) -> bool:
    license_verified_at = candidate.get("license_verified_at")
    background_verified_at = candidate.get("background_check_verified_at")
    if not license_verified_at or not background_verified_at:
        return False
    license_ts = parse_timestamp(str(license_verified_at))
    background_ts = parse_timestamp(str(background_verified_at))
    return not (license_ts > barrier or background_ts > barrier)


def passes_gna_firewall(candidate: dict[str, Any], shift_request: dict[str, Any]) -> bool:
    facility_type = normalize_facility_type(str(shift_request.get("facility_type") or ""))
    required_role = str(shift_request.get("required_role") or "").upper()
    candidate_role = str(candidate.get("role") or "").upper()
    if facility_type != "SNF" or required_role != "CNA":
        return True
    if candidate_role != "CNA":
        return False
    return bool(candidate.get("has_gna_endorsement"))


def role_matches(candidate: dict[str, Any], shift_request: dict[str, Any]) -> bool:
    required_role = str(shift_request.get("required_role") or "").upper()
    candidate_role = str(candidate.get("role") or "").upper()
    if candidate_role == required_role:
        return True
    if required_role == "CNA" and candidate_role == "GNA":
        return True
    return False


def county_rank(candidate: dict[str, Any], shift_request: dict[str, Any]) -> tuple[int, str]:
    facility_county = str(
        shift_request.get("facility_county") or shift_request.get("county") or ""
    ).strip().lower()
    candidate_county = str(candidate.get("county") or "").strip().lower()
    same_county = int(bool(facility_county and facility_county == candidate_county))
    return (same_county, str(candidate.get("provider_id") or candidate.get("full_name") or ""))


def rank_compliant_matches(
    candidates: list[dict[str, Any]],
    shift_request: dict[str, Any],
    evaluation_timestamp: str,
) -> list[dict[str, Any]]:
    if not isinstance(shift_request, dict):
        raise TypeError("shift_request must be a dict")

    barrier = effective_barrier(evaluation_timestamp, shift_request)
    matches: list[dict[str, Any]] = []

    for candidate in candidates:
        if candidate.get("placement_eligible") is False:
            continue
        if not role_matches(candidate, shift_request):
            continue
        if not verification_is_lookahead_safe(candidate, barrier):
            continue
        if not passes_gna_firewall(candidate, shift_request):
            continue

        enriched = dict(candidate)
        enriched["_match_meta"] = {
            "evaluation_barrier_utc": barrier.isoformat(),
            "county_match": county_rank(candidate, shift_request)[0] == 1,
            "matcher_core": "strategy/shift_match_core.py",
        }
        matches.append(enriched)

    matches.sort(key=lambda row: county_rank(row, shift_request), reverse=True)
    return matches
