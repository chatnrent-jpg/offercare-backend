"""Filter open shifts to those a clinician can staff."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandProvider
from app.services.care_taxonomy import (
    clinician_qualifies_for_shift_role,
    credential_valid_in_state,
    provider_supports_facility_type,
)
from app.services.shift_offer_generator import list_open_shifts
from app.services.states import normalize_state
from app.shift_sniper import rate_delta

logger = logging.getLogger(__name__)


def is_demo_walkthrough_provider(provider: MarylandProvider) -> bool:
    return str(provider.email or "").strip().lower().endswith("@offercare.demo")


def shift_matches_provider(
    *,
    provider: MarylandProvider,
    facility_state: str,
    facility_type: str,
    shift_role: str,
    hourly_pay_rate: float,
) -> bool:
    if normalize_state(provider.state) != normalize_state(facility_state):
        return False
    if not credential_valid_in_state(provider.credential_type, provider.state):
        return False
    if not clinician_qualifies_for_shift_role(
        provider.credential_type,
        shift_role,
        facility_state=facility_state,
    ):
        return False
    if not provider_supports_facility_type(provider.service_lines, facility_type):
        return False
    return float(hourly_pay_rate) >= float(provider.min_hourly_rate or 0)


def open_shift_row_from_offer(
    *,
    facility: Any,
    offer: Any,
    county: str | None = None,
    facility_name: str | None = None,
) -> dict:
    """Build an open-shift row dict for broker clearance from ORM objects."""
    starts_at = getattr(offer, "shift_starts_at", None)
    ends_at = getattr(offer, "shift_ends_at", None)
    return {
        "offer_id": str(getattr(offer, "offer_id", "") or ""),
        "facility_id": str(getattr(facility, "facility_id", "") or ""),
        "facility_name": facility_name or str(getattr(facility, "name", "") or ""),
        "county": county or str(getattr(facility, "county", "") or ""),
        "state": str(getattr(facility, "state", "") or ""),
        "facility_type": str(getattr(facility, "facility_type", "") or ""),
        "shift_role": str(getattr(offer, "shift_role", "") or ""),
        "hourly_pay_rate": float(getattr(offer, "hourly_pay_rate", 0) or 0),
        "shift_starts_at": starts_at,
        "shift_ends_at": ends_at,
    }


def provider_matches_open_shift(
    db: Session,
    provider: MarylandProvider,
    row: dict,
) -> bool:
    """Rule gate plus optional UnifiedMatchMatrixBroker schedule/compliance clearance."""
    if not shift_matches_provider(
        provider=provider,
        facility_state=str(row["state"]),
        facility_type=str(row["facility_type"]),
        shift_role=str(row["shift_role"]),
        hourly_pay_rate=float(row["hourly_pay_rate"]),
    ):
        return False
    if is_demo_walkthrough_provider(provider):
        return True
    if not _compliance_sentinel_allows_provider_match(db, provider, row):
        return False
    broker_ok = _broker_confirms_provider_match(db, provider, row)
    if not broker_ok:
        return False
    _run_bias_auditor_on_match(db, provider, row)
    return True


def _run_bias_auditor_on_match(
    db: Session,
    provider: MarylandProvider,
    row: dict,
) -> None:
    if not settings.BIAS_AUDITOR_ENABLED:
        return
    if is_demo_walkthrough_provider(provider):
        return
    try:
        from compliance.algorithmic_bias_auditor import intercept_caregiver_shift_match

        intercept_caregiver_shift_match(db, provider=provider, shift_row=row)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "shift_matching: hb1106 bias auditor fail-open provider=%s offer=%s error=%s",
            provider.provider_id,
            row.get("offer_id"),
            exc,
        )


def _compliance_sentinel_allows_provider_match(
    db: Session,
    provider: MarylandProvider,
    row: dict,
) -> bool:
    from app.middleware.compliance_sentinel import evaluate_compliance_sentinel_for_provider

    verdict = evaluate_compliance_sentinel_for_provider(
        db,
        provider,
        shift_context=_shift_context_from_open_shift(row),
        shift_id=str(row.get("offer_id") or ""),
    )
    if verdict.allowed:
        return True
    logger.info(
        "shift_matching: compliance_sentinel blocked provider=%s status=%s reasons=%s",
        provider.provider_id,
        verdict.compliance_status,
        list(verdict.reasons),
    )
    return False


def _shift_context_from_open_shift(row: dict) -> dict:
    starts_at = row.get("shift_starts_at")
    ends_at = row.get("shift_ends_at")
    return {
        "offer_id": str(row.get("offer_id") or ""),
        "shift_id": str(row.get("offer_id") or ""),
        "facility_id": str(row.get("facility_id") or ""),
        "facility_name": str(row.get("facility_name") or ""),
        "facility_county": str(row.get("county") or ""),
        "county": str(row.get("county") or ""),
        "state": str(row.get("state") or ""),
        "shift_role": str(row.get("shift_role") or ""),
        "facility_type": str(row.get("facility_type") or ""),
        "hourly_pay_rate": float(row.get("hourly_pay_rate") or 0),
        "shift_starts_at": starts_at.isoformat() if isinstance(starts_at, datetime) else starts_at,
        "shift_ends_at": ends_at.isoformat() if isinstance(ends_at, datetime) else ends_at,
    }


def _provider_in_broker_matches(provider: MarylandProvider, matches: list[dict]) -> bool:
    provider_uuid = str(provider.provider_id)
    license_token = str(provider.md_license_number or "").strip().upper()
    for match in matches:
        candidate_id = str(match.get("provider_id") or "").strip()
        license_number = str(match.get("license_number") or "").strip().upper()
        if candidate_id == provider_uuid:
            return True
        if license_token and license_number == license_token:
            return True
        if license_token and candidate_id.upper() == license_token:
            return True
    return False


def _broker_confirms_provider_match(
    db: Session,
    provider: MarylandProvider,
    row: dict,
) -> bool:
    if not settings.UNIFIED_MATCH_MATRIX_BROKER_ENABLED:
        return True
    try:
        from strategy.unified_match_matrix_broker import UnifiedMatchMatrixBroker

        shift_id = str(row.get("offer_id") or "")
        if not shift_id:
            return False
        broker = UnifiedMatchMatrixBroker(db=db)
        try:
            result = broker.resolve_canonical_shift_matches(
                shift_id,
                _shift_context_from_open_shift(row),
            )
        finally:
            broker.close()
        if not result.get("ok"):
            return False
        return _provider_in_broker_matches(provider, list(result.get("matches") or []))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "shift_matching: broker gate fail-open provider=%s offer=%s error=%s",
            provider.provider_id,
            row.get("offer_id"),
            exc,
        )
        return True


def _shift_window_for_row(row: dict) -> tuple[datetime, datetime] | None:
    start = row.get("shift_starts_at")
    end = row.get("shift_ends_at")
    if start is None or end is None:
        return None
    if isinstance(start, datetime) and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if isinstance(end, datetime) and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return start, end


def _schedule_block_preview(
    db: Session,
    provider: MarylandProvider,
    row: dict,
) -> tuple[str | None, bool]:
    window = _shift_window_for_row(row)
    if window is None:
        return None, False
    start, end = window
    try:
        from strategy.clinician_calendar_writer import _provider_calendar_token
        from strategy.schedule_conflict_validator import ScheduleConflictValidator

        token = _provider_calendar_token(provider)
        if not token:
            return None, False
        validator = ScheduleConflictValidator(db=db)
        clearance = validator.evaluate_schedule_clearance(token, start, end)
        conflict_type = str(clearance.get("conflict_type") or "")
        if clearance.get("has_conflict"):
            if conflict_type == "FATIGUE_CAP_EXCEEDED":
                score = clearance.get("fatigue_score")
                suffix = f" (score {float(score):.2f})" if score is not None else ""
                return f"Fatigue cap reached{suffix}", True
            return "Schedule conflict during this shift", True
        if conflict_type == "FATIGUE_ELEVATED":
            score = clearance.get("fatigue_score")
            suffix = f" (score {float(score):.2f})" if score is not None else ""
            return f"Elevated fatigue{suffix} — lock may be blocked", True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "shift_matching: schedule preview failed provider=%s offer=%s error=%s",
            provider.provider_id,
            row.get("offer_id"),
            exc,
        )
    return None, False


def _rule_gate_block_reason(provider: MarylandProvider, row: dict) -> str | None:
    facility_state = str(row["state"])
    facility_type = str(row["facility_type"])
    shift_role = str(row["shift_role"])
    hourly_pay_rate = float(row["hourly_pay_rate"])
    min_rate = float(provider.min_hourly_rate or 0)

    if normalize_state(provider.state) != normalize_state(facility_state):
        return f"Home state {provider.state}; shift is in {facility_state}"
    if not credential_valid_in_state(provider.credential_type, provider.state):
        return f"{provider.credential_type} credential not valid for matching"
    if not clinician_qualifies_for_shift_role(
        provider.credential_type,
        shift_role,
        facility_state=facility_state,
    ):
        return f"{shift_role} needs a different credential than {provider.credential_type}"
    if not provider_supports_facility_type(provider.service_lines, facility_type):
        return f"Not in your care settings ({provider.service_lines or 'none set'})"
    if hourly_pay_rate < min_rate:
        return f"Pay ${hourly_pay_rate:.2f}/hr below your ${min_rate:.2f}/hr minimum"
    return None


def explain_open_shift_lock(
    db: Session,
    provider: MarylandProvider,
    row: dict,
    *,
    broker_matched: bool | None = None,
) -> dict[str, Any]:
    """Explain whether a clinician can lock an open shift row."""
    broadcasting = str(row.get("compliance_lock_status") or "").upper() == "BROADCASTING"
    if not broadcasting:
        status_label = str(row.get("compliance_lock_status") or "UNAVAILABLE").replace("_", " ").title()
        preview = "Already locked" if "LOCK" in status_label.upper() else status_label
        return {
            "lock_eligible": False,
            "lock_preview": preview,
            "rate_delta": None,
            "vault_review_recommended": False,
        }

    rule_block = _rule_gate_block_reason(provider, row)
    if rule_block:
        return {
            "lock_eligible": False,
            "lock_preview": rule_block,
            "rate_delta": None,
            "vault_review_recommended": False,
        }

    matched = (
        broker_matched
        if broker_matched is not None
        else provider_matches_open_shift(db, provider, row)
    )
    pay_delta = round(
        rate_delta(
            shift_pay=float(row["hourly_pay_rate"]),
            min_rate=float(provider.min_hourly_rate or 0),
        ),
        2,
    )
    if matched:
        return {
            "lock_eligible": True,
            "lock_preview": "Ready to lock",
            "rate_delta": pay_delta,
            "vault_review_recommended": False,
        }

    schedule_preview, vault = _schedule_block_preview(db, provider, row)
    if schedule_preview:
        return {
            "lock_eligible": False,
            "lock_preview": schedule_preview,
            "rate_delta": pay_delta,
            "vault_review_recommended": vault,
        }
    return {
        "lock_eligible": False,
        "lock_preview": "Compliance or broker clearance not met",
        "rate_delta": pay_delta,
        "vault_review_recommended": False,
    }


def list_matched_shifts_for_provider(
    db: Session,
    provider: MarylandProvider,
    *,
    limit: int = 50,
    state: str | None = None,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
) -> list[dict]:
    rows = list_open_shifts(
        db,
        limit=max(limit * 4, 100),
        state=state or provider.state,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    matched: list[dict] = []
    for row in rows:
        if not provider_matches_open_shift(db, provider, row):
            continue
        pay_delta = rate_delta(
            shift_pay=float(row["hourly_pay_rate"]),
            min_rate=float(provider.min_hourly_rate or 0),
        )
        matched.append({**row, "rate_delta": round(pay_delta, 2)})
        if len(matched) >= limit:
            break
    return matched


def get_matched_shift_for_provider(
    db: Session,
    provider: MarylandProvider,
    offer_id: UUID,
) -> dict | None:
    from app.services.shift_offer_generator import get_open_shift_by_id

    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        return None
    if not provider_matches_open_shift(db, provider, row):
        return None
    pay_delta = rate_delta(
        shift_pay=float(row["hourly_pay_rate"]),
        min_rate=float(provider.min_hourly_rate or 0),
    )
    return {**row, "rate_delta": round(pay_delta, 2)}


def list_open_shifts_for_clinician(
    db: Session,
    provider: MarylandProvider,
    *,
    limit: int = 50,
    state: str | None = None,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
    lockable_only: bool = False,
) -> list[dict]:
    """All open shifts with per-row lock eligibility for the signed-in clinician."""
    fetch_limit = limit if not lockable_only else max(limit * 4, 100)
    rows = list_open_shifts(
        db,
        limit=fetch_limit,
        state=state,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    enriched: list[dict] = []
    for row in rows:
        rule_block = _rule_gate_block_reason(provider, row)
        if rule_block:
            explained = explain_open_shift_lock(db, provider, row, broker_matched=False)
        else:
            matched = provider_matches_open_shift(db, provider, row)
            explained = explain_open_shift_lock(db, provider, row, broker_matched=matched)
        if lockable_only and not explained.get("lock_eligible"):
            continue
        enriched.append({**row, **explained})
        if len(enriched) >= limit:
            break
    enriched.sort(
        key=lambda item: (
            0 if item.get("lock_eligible") else 1,
            -(float(item.get("rate_delta") or -1)),
        ),
    )
    return enriched


def count_portal_lockable_shifts(
    db: Session,
    provider: MarylandProvider,
    *,
    limit: int = 100,
) -> int:
    rows = list_open_shifts(db, limit=limit)
    total = 0
    for row in rows:
        if str(row.get("compliance_lock_status") or "").upper() != "BROADCASTING":
            continue
        if _rule_gate_block_reason(provider, row):
            continue
        if provider_matches_open_shift(db, provider, row):
            total += 1
    return total
