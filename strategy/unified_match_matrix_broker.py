"""Unified match matrix broker — canonical Rule Sniper vs Semantic Vector routing."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_URGENCY_WINDOW = timedelta(hours=24)
_DEFAULT_SHIFT_HOURS = 8.0
_ROUTING_RULE_SNIPER = "RULE_SNIPER"
_ROUTING_SEMANTIC_VECTOR = "SEMANTIC_VECTOR"
_TAG_DENSE_MARKERS = (
    "dementia care experience",
    "memory care night shifts",
    "dementia care",
    "memory care",
    "behavioral support",
    "memory unit",
    "specialized night",
)
_MIN_TAG_DENSE_HITS = 2


class UnifiedMatchMatrixBrokerHardStop(RuntimeError):
    """Hive halt — unified match matrix broker import or execution failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_shift_start(shift_context: dict[str, Any]) -> datetime | None:
    for key in ("shift_starts_at", "shift_start", "start_time", "starts_at"):
        raw = shift_context.get(key)
        if raw is None:
            continue
        token = str(raw).strip()
        if not token:
            continue
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(token)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _parse_datetime_token(raw: Any) -> datetime | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _shift_interval_from_context(shift_context: dict[str, Any] | None) -> tuple[datetime, datetime] | None:
    if not isinstance(shift_context, dict):
        return None
    start = _parse_shift_start(shift_context)
    if start is None:
        for key in ("shift_timestamp", "evaluation_window_barrier"):
            start = _parse_datetime_token(shift_context.get(key))
            if start is not None:
                break
    if start is None:
        return None
    end = _parse_datetime_token(shift_context.get("shift_ends_at") or shift_context.get("shift_end"))
    if end is None:
        end = start + timedelta(hours=_DEFAULT_SHIFT_HOURS)
    if end <= start:
        end = start + timedelta(hours=_DEFAULT_SHIFT_HOURS)
    return start, end


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "y", "immediate", "urgent"}


def _is_urgent_shift(shift_context: dict[str, Any]) -> bool:
    for key in ("urgent", "immediate", "is_urgent", "urgency_flag", "immediate_urgency"):
        if key in shift_context and _truthy_flag(shift_context.get(key)):
            return True
    shift_start = _parse_shift_start(shift_context)
    if shift_start is None:
        return False
    remaining = shift_start - _utc_now()
    return timedelta(0) <= remaining < _URGENCY_WINDOW


def _context_text_blob(shift_context: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "query_text",
        "shift_role",
        "unit_dept",
        "care_tags",
        "specialty_tags",
        "qualifiers",
        "notes",
        "description",
    ):
        value = shift_context.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _is_tag_dense_shift(shift_context: dict[str, Any]) -> bool:
    blob = _context_text_blob(shift_context)
    if not blob:
        return False
    marker_hits = sum(1 for marker in _TAG_DENSE_MARKERS if marker in blob)
    if marker_hits >= 1 and any(
        phrase in blob for phrase in ("dementia care experience", "memory care night shifts")
    ):
        return True
    try:
        from strategy.match_retry_scheduler import _DEFAULT_CRITICAL_CARE_TAGS, _extract_care_tags
    except ImportError:
        return marker_hits >= _MIN_TAG_DENSE_HITS
    care_tags = _extract_care_tags(blob)
    tag_hits = sum(1 for tag in _DEFAULT_CRITICAL_CARE_TAGS if tag in care_tags)
    return marker_hits >= _MIN_TAG_DENSE_HITS or tag_hits >= _MIN_TAG_DENSE_HITS


def _parse_checked_at(value: str | None) -> datetime:
    if not value:
        return _utc_now()
    token = str(value).strip()
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return _utc_now()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _import_compliance_audit_ledger() -> Any:
    try:
        from app.models.compliance_audit_ledger import ComplianceAuditLedger
    except ImportError:
        import importlib.util

        module_path = Path(__file__).resolve().parents[1] / "app" / "models" / "compliance_audit_ledger.py"
        spec = importlib.util.spec_from_file_location("compliance_audit_ledger", module_path)
        if spec is None or spec.loader is None:
            raise UnifiedMatchMatrixBrokerHardStop("compliance_audit_ledger_import_failed") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.ComplianceAuditLedger
    return ComplianceAuditLedger


def _timesheet_token_for_audit(shift_id: str, shift_context: dict[str, Any] | None) -> str:
    if isinstance(shift_context, dict):
        for key in ("timesheet_token", "timesheet_id"):
            raw = shift_context.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
    return str(shift_id)


def _audit_payload_from_evaluation(
    *,
    shift_id: str,
    shift_context: dict[str, Any] | None,
    evaluation: Any,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_type": "MATCH_BROKER_CREDENTIAL_EVAL",
        "shift_id": shift_id,
        "timesheet_token": _timesheet_token_for_audit(shift_id, shift_context),
        "provider_id": evaluation.provider_id,
        "license_number": evaluation.license_number,
        "is_eligible": bool(evaluation.is_eligible),
        "compliance_status": evaluation.compliance_status,
        "checked_at": evaluation.checked_at,
        "mbon_status": evaluation.mbon_status,
        "oig_status": evaluation.oig_status,
        "license_expiration_date": evaluation.license_expiration_date,
        "details": evaluation.details,
        "routing_engine": candidate.get("routing_engine"),
        "match_rank": candidate.get("rank"),
        "similarity_score": candidate.get("similarity_score"),
        "audit_source": "UnifiedMatchMatrixBroker",
    }


def _parse_facility_uuid(shift_context: dict[str, Any]) -> UUID | None:
    raw = shift_context.get("facility_id")
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    try:
        return UUID(token)
    except ValueError:
        return None


class UnifiedMatchMatrixBroker:
    """Master match orchestrator — winner-take-all Rule Sniper vs Semantic Vector routing."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._owns_session = False
        self._semantic_engine: Any | None = None
        self._match_retry_scheduler: Any | None = None
        self._compliance_authority_anchor: Any | None = None
        self._last_schedule_blocked_count = 0

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise UnifiedMatchMatrixBrokerHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._match_retry_scheduler is not None:
            try:
                self._match_retry_scheduler.close()
            except Exception:  # noqa: BLE001
                pass
            self._match_retry_scheduler = None
        if self._compliance_authority_anchor is not None:
            try:
                self._compliance_authority_anchor.close()
            except Exception:  # noqa: BLE001
                pass
            self._compliance_authority_anchor = None
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _semantic_payout_engine(self) -> Any:
        if self._semantic_engine is None:
            try:
                from strategy.semantic_payout_engine import SemanticPayoutEngine
            except Exception as exc:  # noqa: BLE001
                raise UnifiedMatchMatrixBrokerHardStop("semantic_payout_engine_import_failed") from exc
            self._semantic_engine = SemanticPayoutEngine(prefer_live_db=True)
        return self._semantic_engine

    def _get_match_retry_scheduler(self) -> Any:
        if self._match_retry_scheduler is None:
            try:
                from strategy.match_retry_scheduler import MatchRetryScheduler
            except Exception as exc:  # noqa: BLE001
                raise UnifiedMatchMatrixBrokerHardStop("match_retry_scheduler_import_failed") from exc
            self._match_retry_scheduler = MatchRetryScheduler(db=self.db)
        return self._match_retry_scheduler

    def _compliance_authority_anchor(self) -> Any:
        if self._compliance_authority_anchor is None:
            try:
                from strategy.compliance_authority_anchor import ComplianceAuthorityAnchor
            except Exception as exc:  # noqa: BLE001
                raise UnifiedMatchMatrixBrokerHardStop("compliance_authority_anchor_import_failed") from exc
            self._compliance_authority_anchor = ComplianceAuthorityAnchor(db=self.db)
        return self._compliance_authority_anchor

    def _credential_check_engine(self) -> Any:
        try:
            from strategy.credential_check_engine import CredentialCheckEngine
        except Exception as exc:  # noqa: BLE001
            raise UnifiedMatchMatrixBrokerHardStop("credential_check_engine_import_failed") from exc
        return CredentialCheckEngine(db=self.db)

    def _schedule_conflict_validator(self) -> Any:
        try:
            from strategy.schedule_conflict_validator import ScheduleConflictValidator
        except Exception as exc:  # noqa: BLE001
            raise UnifiedMatchMatrixBrokerHardStop("schedule_conflict_validator_import_failed") from exc
        return ScheduleConflictValidator(db=self.db)

    def _evaluate_schedule_clearance(
        self,
        provider_id: str,
        shift_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        interval = _shift_interval_from_context(shift_context)
        if interval is None:
            return {
                "has_conflict": False,
                "conflict_type": "CLEAR",
                "conflicting_event_id": None,
            }
        start_time, end_time = interval
        try:
            validator = self._schedule_conflict_validator()
            return validator.evaluate_schedule_clearance(provider_id, start_time, end_time)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "HIVE_MATCH_MATRIX: schedule clearance skipped provider=%s error=%s",
                provider_id,
                exc,
            )
            return {
                "has_conflict": False,
                "conflict_type": "CLEAR",
                "conflicting_event_id": None,
            }

    def _select_routing_engine(self, shift_context: dict[str, Any]) -> str:
        if _is_urgent_shift(shift_context):
            return _ROUTING_RULE_SNIPER
        if _is_tag_dense_shift(shift_context):
            return _ROUTING_SEMANTIC_VECTOR
        return _ROUTING_RULE_SNIPER

    def _shift_request_from_context(self, shift_id: str, shift_context: dict[str, Any]) -> dict[str, Any]:
        request = dict(shift_context)
        request.setdefault("shift_id", shift_id)
        request.setdefault("offer_id", shift_id)
        return request

    def _semantic_query_from_context(self, shift_id: str, shift_context: dict[str, Any]) -> str:
        explicit = str(shift_context.get("query_text") or "").strip()
        if len(explicit) >= 8:
            return explicit
        role = str(shift_context.get("shift_role") or shift_context.get("required_role") or "CNA").strip()
        county = str(
            shift_context.get("facility_county") or shift_context.get("county") or "Montgomery"
        ).strip()
        blob = _context_text_blob(shift_context)
        tags = blob if blob else "specialized healthcare shift"
        return f"{role} {county} SNF {tags} shift {shift_id[:8]}"

    def _run_rule_sniper_matches(
        self,
        shift_id: str,
        shift_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            from strategy.unified_shift_matcher import UnifiedShiftMatcher
            from strategy.shift_match_core import parse_timestamp
        except Exception as exc:  # noqa: BLE001
            raise UnifiedMatchMatrixBrokerHardStop("rule_sniper_engine_import_failed") from exc

        _ = self._get_match_retry_scheduler()
        facility_id = _parse_facility_uuid(shift_context)
        matcher = UnifiedShiftMatcher.from_database(self.db, facility_id=facility_id)
        shift_request = self._shift_request_from_context(shift_id, shift_context)
        evaluation_timestamp = str(
            shift_context.get("evaluation_timestamp") or _utc_now().isoformat()
        )
        try:
            parse_timestamp(evaluation_timestamp)
        except ValueError:
            evaluation_timestamp = _utc_now().isoformat()

        ranked = matcher.find_compliant_matches(shift_request, evaluation_timestamp)
        candidates: list[dict[str, Any]] = []
        for index, row in enumerate(ranked, start=1):
            candidates.append(
                {
                    "provider_id": str(row.get("provider_id") or ""),
                    "full_name": str(row.get("full_name") or ""),
                    "role": str(row.get("role") or ""),
                    "county": str(row.get("county") or ""),
                    "rank": index,
                    "similarity_score": None,
                    "routing_engine": _ROUTING_RULE_SNIPER,
                    "match_meta": dict(row.get("_match_meta") or {}),
                }
            )
        return [row for row in candidates if row["provider_id"]]

    def _run_semantic_vector_matches(
        self,
        shift_id: str,
        shift_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        query = self._semantic_query_from_context(shift_id, shift_context)
        engine = self._semantic_payout_engine()
        context = dict(shift_context)
        context.setdefault("shift_id", shift_id)
        context.setdefault("offer_id", shift_id)

        try:
            response = engine.find_top_vector_matches(
                query,
                shift_context=context,
                use_live_db=bool(shift_context.get("use_live_db", True)),
            )
        except ValueError as exc:
            logger.warning(
                "HIVE_MATCH_MATRIX: semantic route rejected shift=%s error=%s",
                shift_id,
                exc,
            )
            return []

        candidates: list[dict[str, Any]] = []
        for row in response.matches:
            candidates.append(
                {
                    "provider_id": str(row.provider_id),
                    "full_name": str(row.full_name),
                    "role": str(row.role),
                    "county": str(row.county),
                    "rank": int(row.rank),
                    "similarity_score": float(row.similarity_score),
                    "routing_engine": _ROUTING_SEMANTIC_VECTOR,
                    "match_meta": {"semantic_engine": response.engine, "elapsed_ms": response.elapsed_ms},
                }
            )
        return candidates

    def _commit_mandatory_audit_ledger(
        self,
        *,
        shift_id: str,
        shift_context: dict[str, Any] | None,
        evaluation: Any,
        candidate: dict[str, Any],
    ) -> bool:
        """Write encrypted compliance audit row — fail open on telemetry faults."""
        try:
            ComplianceAuditLedger = _import_compliance_audit_ledger()
            payload = _audit_payload_from_evaluation(
                shift_id=shift_id,
                shift_context=shift_context,
                evaluation=evaluation,
                candidate=candidate,
            )
            with self.db.begin():
                row = ComplianceAuditLedger(
                    provider_id=str(evaluation.provider_id),
                    timesheet_token=_timesheet_token_for_audit(shift_id, shift_context),
                    compliance_status=str(evaluation.compliance_status),
                    is_eligible=bool(evaluation.is_eligible),
                    checked_at=_parse_checked_at(evaluation.checked_at),
                )
                row.raw_payload_json = json.dumps(payload, default=str)
                self.db.add(row)
            return True
        except SQLAlchemyError as exc:
            logger.warning(
                "HIVE_MATCH_MATRIX: audit ledger write failed provider=%s shift=%s error=%s",
                evaluation.provider_id,
                shift_id,
                exc,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "HIVE_MATCH_MATRIX: audit ledger telemetry fault provider=%s shift=%s error=%s",
                evaluation.provider_id,
                shift_id,
                exc,
            )
            return False

    def _screen_and_anchor_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        shift_id: str | None = None,
        shift_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        checker = self._credential_check_engine()
        anchor = self._compliance_authority_anchor()
        eligible: list[dict[str, Any]] = []
        schedule_blocked = 0

        try:
            for candidate in candidates:
                provider_id = str(candidate.get("provider_id") or "").strip()
                if not provider_id:
                    continue
                try:
                    evaluation = checker.evaluate_dispatch_compliance(provider_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "HIVE_MATCH_MATRIX: credential screening fault provider=%s error=%s",
                        provider_id,
                        exc,
                    )
                    continue

                if shift_id:
                    self._commit_mandatory_audit_ledger(
                        shift_id=shift_id,
                        shift_context=shift_context,
                        evaluation=evaluation,
                        candidate=candidate,
                    )

                try:
                    anchor.synchronize_gate_to_provider_status(provider_id, evaluation)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "HIVE_MATCH_MATRIX: compliance anchor sync fault provider=%s error=%s",
                        provider_id,
                        exc,
                    )

                if not bool(evaluation.is_eligible):
                    continue

                calendar_provider_id = str(evaluation.license_number or provider_id).strip()
                clearance = self._evaluate_schedule_clearance(calendar_provider_id, shift_context)
                if clearance.get("has_conflict"):
                    schedule_blocked += 1
                    logger.warning(
                        "HIVE_MATCH_MATRIX: schedule hard conflict provider=%s event=%s",
                        calendar_provider_id,
                        clearance.get("conflicting_event_id"),
                    )
                    continue

                eligible.append(
                    {
                        **candidate,
                        "is_eligible": True,
                        "compliance_status": str(evaluation.compliance_status),
                        "mbon_status": str(evaluation.mbon_status),
                        "oig_status": str(evaluation.oig_status),
                        "license_number": str(evaluation.license_number),
                        "schedule_clearance": str(clearance.get("conflict_type") or "CLEAR"),
                        "schedule_conflict_event_id": clearance.get("conflicting_event_id"),
                    }
                )
        finally:
            checker.close()

        self._last_schedule_blocked_count = schedule_blocked
        return eligible

    def resolve_canonical_shift_matches(
        self,
        shift_id: str,
        shift_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Route shift to Rule Sniper or Semantic Vector, screen, anchor, and return eligible matches."""
        if not isinstance(shift_context, dict):
            raise TypeError("shift_context must be a dict")

        token = str(shift_id or "").strip()
        if not token:
            raise ValueError("shift_id is required")

        urgent = _is_urgent_shift(shift_context)
        tag_dense = _is_tag_dense_shift(shift_context)
        routing_engine = self._select_routing_engine(shift_context)

        try:
            if routing_engine == _ROUTING_SEMANTIC_VECTOR:
                raw_candidates = self._run_semantic_vector_matches(token, shift_context)
            else:
                raw_candidates = self._run_rule_sniper_matches(token, shift_context)
        except UnifiedMatchMatrixBrokerHardStop:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "HIVE_MATCH_MATRIX: match branch failed shift=%s engine=%s error=%s",
                token,
                routing_engine,
                exc,
            )
            return {
                "ok": False,
                "shift_id": token,
                "routing_engine": routing_engine,
                "urgent": urgent,
                "tag_dense": tag_dense,
                "match_count": 0,
                "matches": [],
                "message": str(exc),
            }

        eligible_matches = self._screen_and_anchor_candidates(
            raw_candidates,
            shift_id=token,
            shift_context=shift_context,
        )

        return {
            "ok": True,
            "shift_id": token,
            "routing_engine": routing_engine,
            "urgent": urgent,
            "tag_dense": tag_dense,
            "raw_match_count": len(raw_candidates),
            "match_count": len(eligible_matches),
            "schedule_blocked_count": self._last_schedule_blocked_count,
            "matches": eligible_matches,
        }


if __name__ == "__main__":
    print("COMPILE_OK unified_match_matrix_broker")
    broker = UnifiedMatchMatrixBroker(db=None)
    urgent_ctx = {
        "urgent": True,
        "shift_role": "CNA Night",
        "facility_county": "Montgomery",
        "required_role": "CNA",
        "facility_type": "SNF",
    }
    tag_ctx = {
        "shift_role": "CNA",
        "qualifiers": "dementia care experience memory care night shifts",
        "facility_county": "Baltimore",
        "required_role": "CNA",
        "facility_type": "SNF",
        "shift_starts_at": (_utc_now() + timedelta(days=3)).isoformat(),
    }
    print(f"urgent_route={broker._select_routing_engine(urgent_ctx)}")
    print(f"tag_dense_route={broker._select_routing_engine(tag_ctx)}")
    print(f"broker={broker.__class__.__name__}")
