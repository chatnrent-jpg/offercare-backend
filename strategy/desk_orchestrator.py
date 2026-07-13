"""Maryland ops desk orchestrator — chains all isolated strategy engines (staging)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from strategy.backup_routing_engine import BackupRoutingEngine
from strategy.db_workforce_adapter import candidates_from_registry
from strategy.placement_penalty_engine import PlacementPenaltyEngine
from strategy.schedule_conflict_engine import ScheduleConflictEngine
from strategy.surge_pricing_engine import SurgePricingEngine
from strategy.unified_shift_matcher import UnifiedShiftMatcher

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PIPELINE_LOG = _REPO_ROOT / "logs" / "manus" / "desk_pipeline_runs.json"
_DEFAULT_MANUS_HANDOFF = _REPO_ROOT / "logs" / "manus" / "manus_desk_handoff.json"
_DEFAULT_SHIFT_HOURS = 8.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: str) -> datetime:
    token = str(value or "").strip()
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _shift_start_key(shift: dict[str, Any]) -> str:
    for key in ("shift_timestamp", "start_time", "shift_start"):
        raw = shift.get(key)
        if raw:
            return str(raw)
    raise ValueError("shift must include shift_timestamp or start_time")


def _shift_interval(shift: dict[str, Any], duration_hours: float = _DEFAULT_SHIFT_HOURS) -> tuple[str, str]:
    start = _parse_timestamp(_shift_start_key(shift))
    end = start + timedelta(hours=duration_hours)
    return start.isoformat(), end.isoformat()


def _matcher_candidates_from_registry(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return candidates_from_registry(registry)


def commitments_from_timesheets(timesheets_payload: dict[str, Any]) -> list[dict[str, Any]]:
    commitments: list[dict[str, Any]] = []
    for row in timesheets_payload.get("timesheets") or []:
        if str(row.get("status") or "").upper() != "RECONCILED":
            continue
        shift = {
            "shift_timestamp": row.get("shift_timestamp"),
            "county": row.get("county"),
        }
        start_iso, end_iso = _shift_interval(
            shift,
            duration_hours=float(row.get("hours_worked") or row.get("scheduled_hours") or _DEFAULT_SHIFT_HOURS),
        )
        commitments.append(
            {
                "provider_id": row.get("provider_license_number"),
                "provider_name": row.get("provider_name"),
                "order_id": row.get("order_id"),
                "facility_name": row.get("facility_name"),
                "county": row.get("county"),
                "shift_start": start_iso,
                "shift_end": end_iso,
            }
        )
    return commitments


def provider_hours_from_timesheets(
    timesheets_payload: dict[str, Any],
    provider_id: str,
) -> float:
    total = 0.0
    for row in timesheets_payload.get("timesheets") or []:
        if str(row.get("provider_license_number") or "") != str(provider_id):
            continue
        total += float(row.get("hours_worked") or 0.0)
    return total


class DeskOrchestrator:
    """Runs match → conflict → surge → optional backup/penalty in one auditable pipeline."""

    def __init__(
        self,
        workforce_registry: dict[str, Any],
        active_commitments: list[dict[str, Any]] | None = None,
        *,
        timesheets_payload: dict[str, Any] | None = None,
        db: Any | None = None,
        facility_id: Any | None = None,
    ) -> None:
        if not isinstance(workforce_registry, dict):
            raise TypeError("workforce_registry must be a dict")
        self.workforce_registry = dict(workforce_registry)
        if active_commitments is not None:
            self.commitments = list(active_commitments)
        elif timesheets_payload:
            self.commitments = commitments_from_timesheets(timesheets_payload)
        else:
            self.commitments = []
        self.timesheets_payload = dict(timesheets_payload or {})

        if db is not None:
            self.matcher = UnifiedShiftMatcher.from_database(db, facility_id=facility_id)
            self.matcher_source = "postgresql"
        else:
            self.matcher = UnifiedShiftMatcher.from_registry(self.workforce_registry)
            self.matcher_source = "registry"
        self.conflict_engine = ScheduleConflictEngine(self.commitments)
        self.surge_engine = SurgePricingEngine()
        self.backup_engine = BackupRoutingEngine(self.workforce_registry)
        self.penalty_engine = PlacementPenaltyEngine()

    def _normalize_shift_request(self, shift: dict[str, Any]) -> dict[str, Any]:
        return {
            "order_id": shift.get("order_id"),
            "facility_name": shift.get("facility_name"),
            "facility_type": shift.get("facility_type"),
            "required_role": shift.get("required_role"),
            "county": shift.get("county"),
            "facility_county": shift.get("county"),
            "shift_timestamp": _shift_start_key(shift),
            "evaluation_window_barrier": _shift_start_key(shift),
        }

    def _proposed_booking(self, shift: dict[str, Any]) -> dict[str, Any]:
        start_iso, end_iso = _shift_interval(shift)
        return {
            "shift_start": start_iso,
            "shift_end": end_iso,
            "county": shift.get("county"),
            "facility_name": shift.get("facility_name"),
            "order_id": shift.get("order_id"),
        }

    def run_booking_pipeline(
        self,
        shift: dict[str, Any],
        evaluation_timestamp: str,
        request_timestamp: str | None = None,
    ) -> dict[str, Any]:
        shift_request = self._normalize_shift_request(shift)
        request_ts = request_timestamp or evaluation_timestamp
        matches = self.matcher.find_compliant_matches(shift_request, evaluation_timestamp)

        booking_candidates: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None

        for match in matches:
            provider_id = str(match.get("provider_id") or "")
            safe, reason = self.conflict_engine.validate_booking_safety(
                provider_id,
                self._proposed_booking(shift),
            )
            row = {
                "provider_id": provider_id,
                "full_name": match.get("full_name"),
                "county": match.get("county"),
                "county_match": match.get("_match_meta", {}).get("county_match"),
                "has_gna_endorsement": match.get("has_gna_endorsement"),
                "conflict_safe": safe,
                "conflict_reason": reason,
            }
            booking_candidates.append(row)
            if safe and selected is None:
                selected = row

        surge = self.surge_engine.calculate_surge_rate(shift_request, request_ts)

        status = "BOOKING_READY" if selected else "NO_SAFE_ASSIGNMENT"
        if matches and not selected:
            status = "CONFLICT_BLOCKED"

        return {
            "pipeline": "BOOKING",
            "status": status,
            "shift": shift_request,
            "evaluation_timestamp": evaluation_timestamp,
            "request_timestamp": request_ts,
            "match_count": len(matches),
            "matcher_source": self.matcher_source,
            "selected_provider": selected,
            "booking_candidates": booking_candidates[:5],
            "surge_pricing": surge,
            "active_commitments_count": len(self.commitments),
        }

    def run_callout_pipeline(
        self,
        disrupted_shift_id: str,
        original_provider_id: str,
    ) -> dict[str, Any]:
        dispatch = self.backup_engine.trigger_backup_routing(
            disrupted_shift_id=disrupted_shift_id,
            original_provider_id=original_provider_id,
        )
        return {
            "pipeline": "CALLOUT",
            "status": dispatch.get("status"),
            "dispatch": dispatch,
        }

    def run_penalty_pipeline(
        self,
        facility_id: str,
        provider_id: str,
        total_hours_worked: float | None = None,
    ) -> dict[str, Any]:
        hours = (
            float(total_hours_worked)
            if total_hours_worked is not None
            else provider_hours_from_timesheets(self.timesheets_payload, provider_id)
        )
        audit = self.penalty_engine.audit_permanent_placement(
            facility_id=facility_id,
            provider_id=provider_id,
            total_hours_worked=hours,
        )
        return {
            "pipeline": "PENALTY_AUDIT",
            "status": "VIOLATION" if audit["is_contract_violation"] else "CLEAR",
            "audit": audit,
        }

    def run_full_desk_cycle(
        self,
        shift: dict[str, Any],
        evaluation_timestamp: str,
        request_timestamp: str | None = None,
        *,
        facility_id: str | None = None,
        penalty_provider_id: str | None = None,
    ) -> dict[str, Any]:
        booking = self.run_booking_pipeline(shift, evaluation_timestamp, request_timestamp)
        callout: dict[str, Any] | None = None
        penalty: dict[str, Any] | None = None

        if booking.get("status") == "BOOKING_READY" and booking.get("selected_provider"):
            provider_id = str(booking["selected_provider"]["provider_id"])
            if penalty_provider_id and provider_id == penalty_provider_id:
                penalty = self.run_penalty_pipeline(
                    facility_id=facility_id or f"MD-SNF-{str(shift.get('facility_name', 'UNKNOWN'))[:12].upper().replace(' ', '-')}",
                    provider_id=provider_id,
                )

        return {
            "run_id": f"desk-{_utc_now_iso()}",
            "staged_at_utc": _utc_now_iso(),
            "live_execution": False,
            "mode": "STAGING",
            "product": "VettedMe.ai Maryland Desk Orchestrator",
            "booking": booking,
            "callout": callout,
            "penalty": penalty,
            "manus_operator_note": "Manus acts on filesystem/API handoff · VettedMe decides via engine chain.",
        }

    @staticmethod
    def persist_run(payload: dict[str, Any], log_path: Path | None = None) -> Path:
        target = log_path or _DEFAULT_PIPELINE_LOG
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.is_file():
            existing = json.loads(target.read_text(encoding="utf-8"))
            runs = existing.get("runs") if isinstance(existing.get("runs"), list) else []
        else:
            existing = {
                "mode": "STAGING",
                "live_execution": False,
                "product": "VettedMe.ai Desk Pipeline Runs",
                "runs": [],
            }
            runs = []

        runs.append(payload)
        existing["runs"] = runs
        existing["count"] = len(runs)
        existing["updated_at_utc"] = _utc_now_iso()
        target.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target

    @staticmethod
    def write_manus_handoff(manifest: dict[str, Any], path: Path | None = None) -> Path:
        target = path or _DEFAULT_MANUS_HANDOFF
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target


def build_manus_desk_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _REPO_ROOT
    return {
        "schema_version": "1.0",
        "product": "VettedMe.ai Maryland Ops Desk — Manus Handoff",
        "architecture": "Manus acts (scrape, stage JSON, trigger scripts) · VettedMe decides (engine chain)",
        "live_execution": False,
        "operator_workflows": [
            {
                "id": "stage-workforce",
                "title": "Process nurse applicants",
                "command": "python scripts/process_nurse_applicants.py",
                "output": "logs/manus/processed_providers.json",
            },
            {
                "id": "stage-shifts",
                "title": "Simulate active shift orders",
                "command": "python scripts/simulate_shift_orders.py",
                "output": "logs/manus/active_shifts.json",
            },
            {
                "id": "stage-timesheets",
                "title": "Reconcile timesheets",
                "command": "python scripts/process_timesheets.py",
                "output": "logs/manus/reconciled_timesheets.json",
            },
            {
                "id": "run-desk-pipeline",
                "title": "Execute full desk orchestrator",
                "command": "python scripts/run_desk_pipeline.py",
                "output": "logs/manus/desk_pipeline_runs.json",
            },
        ],
        "engine_chain": [
            "strategy/shift_match_core.py",
            "strategy/unified_shift_matcher.py",
            "strategy/db_workforce_adapter.py",
            "strategy/schedule_conflict_engine.py",
            "strategy/surge_pricing_engine.py",
            "strategy/backup_routing_engine.py",
            "strategy/placement_penalty_engine.py",
            "strategy/desk_orchestrator.py",
        ],
        "filesystem_paths": {
            "repo_root": str(root),
            "processed_providers": str(root / "logs/manus/processed_providers.json"),
            "active_shifts": str(root / "logs/manus/active_shifts.json"),
            "reconciled_timesheets": str(root / "logs/manus/reconciled_timesheets.json"),
            "backup_dispatches": str(root / "logs/manus/backup_dispatches.json"),
            "desk_pipeline_runs": str(root / "logs/manus/desk_pipeline_runs.json"),
            "ops_console": str(root / "ui_dashboard/ops_console.py"),
        },
        "api_recruitment_prefix": "/api/vettedme/manus/recruitment",
        "api_credential_prefix": "/api/vettedme/manus",
        "generated_at_utc": _utc_now_iso(),
    }


if __name__ == "__main__":
    import tempfile

    mock_registry = {
        "applicants": [
            {
                "name": "Aisha Thompson",
                "license_type": "CNA",
                "license_number": "CNA-MD-88421",
                "has_gna_endorsement": True,
                "county": "Montgomery",
                "verification_timestamp": "2026-06-20T14:30:00+00:00",
                "placement_eligible": True,
            },
            {
                "name": "Elena Vasquez",
                "license_type": "CNA",
                "license_number": "CNA-MD-90331",
                "has_gna_endorsement": True,
                "county": "Anne Arundel",
                "verification_timestamp": "2026-06-18T08:20:00+00:00",
                "placement_eligible": True,
            },
        ]
    }
    mock_timesheets = {
        "timesheets": [
            {
                "status": "RECONCILED",
                "order_id": "eb1ac566-7331-4af0-aa14-6a7077614773",
                "provider_license_number": "CNA-MD-88421",
                "provider_name": "Aisha Thompson",
                "facility_name": "Arbor Ridge at Riderwood",
                "county": "Montgomery",
                "shift_timestamp": "2026-06-27T07:00:00+00:00",
                "hours_worked": 8.0,
            }
        ]
    }
    shift = {
        "order_id": "new-order-montgomery",
        "facility_name": "FutureCare Northpoint",
        "facility_type": "SNF",
        "county": "Montgomery",
        "required_role": "CNA",
        "shift_timestamp": "2026-06-28T07:00:00+00:00",
    }

    orchestrator = DeskOrchestrator(mock_registry, timesheets_payload=mock_timesheets)
    result = orchestrator.run_full_desk_cycle(
        shift,
        evaluation_timestamp="2026-06-27T10:00:00+00:00",
    )
    assert result["booking"]["status"] in {"BOOKING_READY", "CONFLICT_BLOCKED", "NO_SAFE_ASSIGNMENT"}
    assert "surge_pricing" in result["booking"]

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "desk_pipeline_runs.json"
        DeskOrchestrator.persist_run(result, log_path)
        assert log_path.is_file()

    print("DeskOrchestrator self-test passed.")
