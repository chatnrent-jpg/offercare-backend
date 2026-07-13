"""Maryland ops desk pipeline — API/service layer over strategy/desk_orchestrator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.config import settings
from strategy.desk_orchestrator import DeskOrchestrator, build_manus_desk_manifest

PipelineMode = Literal["booking", "callout", "penalty", "full"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"staging file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _staging_paths() -> dict[str, Path]:
    root = _repo_root()
    return {
        "providers": root / "logs" / "manus" / "processed_providers.json",
        "shifts": root / "logs" / "manus" / "active_shifts.json",
        "timesheets": root / "logs" / "manus" / "reconciled_timesheets.json",
        "pipeline_log": root / "logs" / "manus" / "desk_pipeline_runs.json",
        "handoff": root / "logs" / "manus" / "manus_desk_handoff.json",
    }


def _base_url() -> str:
    configured = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    return configured or "http://127.0.0.1:8000"


def build_manus_desk_handoff() -> dict[str, Any]:
    manifest = build_manus_desk_manifest(_repo_root())
    prefix = f"{_base_url()}/api/vettedme/manus/desk"
    manifest["api_endpoints"] = {
        "handoff": f"{prefix}/handoff",
        "run": f"{prefix}/run",
        "run_production": f"{prefix}/run-production",
        "run_production_live": f"{prefix}/run-production-live",
    }
    manifest["auth_header"] = "X-Manus-Key"
    return manifest


def _resolve_shift(shifts_payload: dict[str, Any], order_id: str | None) -> dict[str, Any]:
    shifts = shifts_payload.get("shifts") or []
    if not shifts:
        raise ValueError("no shifts in active_shifts.json")
    if not order_id:
        return dict(shifts[0])
    for shift in shifts:
        if str(shift.get("order_id") or "") == str(order_id):
            return dict(shift)
    raise ValueError(f"shift not found: {order_id}")


def run_md_desk_pipeline(
    *,
    pipeline: PipelineMode = "full",
    order_id: str | None = None,
    evaluation_timestamp: str | None = None,
    request_timestamp: str | None = None,
    disrupted_shift_id: str | None = None,
    original_provider_id: str | None = None,
    facility_id: str | None = None,
    provider_id: str | None = None,
    total_hours_worked: float | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    paths = _staging_paths()
    providers = _load_json(paths["providers"])
    shifts_payload = _load_json(paths["shifts"])
    timesheets = _load_json(paths["timesheets"])

    evaluation_ts = evaluation_timestamp or datetime.now(timezone.utc).isoformat()
    orchestrator = DeskOrchestrator(providers, timesheets_payload=timesheets)

    if pipeline == "booking":
        shift = _resolve_shift(shifts_payload, order_id)
        result = orchestrator.run_booking_pipeline(shift, evaluation_ts, request_timestamp)
        status = str(result.get("status") or "UNKNOWN")
    elif pipeline == "callout":
        shift = _resolve_shift(shifts_payload, disrupted_shift_id or order_id)
        disrupted_id = disrupted_shift_id or str(shift.get("order_id") or "")
        original_id = original_provider_id or "CNA-MD-88421"
        result = orchestrator.run_callout_pipeline(disrupted_id, original_id)
        status = str(result.get("status") or "UNKNOWN")
    elif pipeline == "penalty":
        audit_provider = provider_id or "CNA-MD-88421"
        audit_facility = facility_id or "MD-SNF-ARBOR-RIDGE"
        hours = total_hours_worked if total_hours_worked is not None else 45.0
        result = orchestrator.run_penalty_pipeline(audit_facility, audit_provider, hours)
        status = str(result.get("status") or "UNKNOWN")
    else:
        shift = _resolve_shift(shifts_payload, order_id)
        result = orchestrator.run_full_desk_cycle(
            shift,
            evaluation_timestamp=evaluation_ts,
            request_timestamp=request_timestamp,
            facility_id=facility_id,
            penalty_provider_id=provider_id,
        )
        status = str(result.get("booking", {}).get("status") or "UNKNOWN")

    run_id = f"desk-api-{datetime.now(timezone.utc).isoformat()}"
    envelope = {
        "run_id": run_id,
        "staged_at_utc": datetime.now(timezone.utc).isoformat(),
        "live_execution": False,
        "mode": "STAGING",
        "pipeline": pipeline,
        "status": status,
        "result": result,
    }

    log_path = paths["pipeline_log"]
    handoff_path = paths["handoff"]
    if persist:
        DeskOrchestrator.persist_run(envelope, log_path)
        DeskOrchestrator.write_manus_handoff(build_manus_desk_handoff(), handoff_path)

    return {
        "ok": True,
        "run_id": run_id,
        "pipeline": pipeline,
        "status": status,
        "live_execution": False,
        "result": result,
        "log_path": str(log_path.relative_to(_repo_root())).replace("\\", "/"),
        "handoff_path": str(handoff_path.relative_to(_repo_root())).replace("\\", "/"),
    }


def run_md_desk_pipeline_production(
    db,
    *,
    evaluation_timestamp: str | None = None,
    request_timestamp: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    from app.services.md_desk_production_loader import run_production_desk_cycle

    result = run_production_desk_cycle(
        db,
        evaluation_timestamp=evaluation_timestamp,
        request_timestamp=request_timestamp,
        persist=persist,
    )
    paths = _staging_paths()
    if persist:
        DeskOrchestrator.write_manus_handoff(build_manus_desk_handoff(), paths["handoff"])
    result["log_path"] = str(paths["pipeline_log"].relative_to(_repo_root())).replace("\\", "/")
    result["handoff_path"] = str(paths["handoff"].relative_to(_repo_root())).replace("\\", "/")
    return result


def run_md_desk_production_live_callout(db, *, original_provider_id: str = "CNA-MD-88421") -> dict[str, Any]:
    from app.services.md_desk_production_loader import run_production_live_callout

    result = run_production_live_callout(db, original_provider_id=original_provider_id)
    paths = _staging_paths()
    DeskOrchestrator.write_manus_handoff(build_manus_desk_handoff(), paths["handoff"])
    result["dispatch_log_path"] = str(
        (paths["handoff"].parent / "backup_dispatches.json").relative_to(_repo_root())
    ).replace("\\", "/")
    return result
