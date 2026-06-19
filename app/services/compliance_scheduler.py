"""Background compliance monitor — document expiration sweeps and dispatch suspension."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.compliance_monitor import run_compliance_monitor
from app.services.ops_metrics import log_ops_event

logger = logging.getLogger(__name__)

_stop_event: asyncio.Event | None = None
_task: asyncio.Task | None = None
_last_run_at: datetime | None = None
_last_summary: dict | None = None


@dataclass(frozen=True)
class ComplianceSchedulerStatus:
    enabled: bool
    interval_seconds: int
    running: bool
    last_run_at: datetime | None
    last_documents_checked: int | None
    last_suspended_count: int | None


def compliance_scheduler_status() -> ComplianceSchedulerStatus:
    return ComplianceSchedulerStatus(
        enabled=settings.COMPLIANCE_MONITOR_WORKER_ENABLED,
        interval_seconds=settings.COMPLIANCE_MONITOR_WORKER_INTERVAL_SECONDS,
        running=_task is not None and not _task.done(),
        last_run_at=_last_run_at,
        last_documents_checked=(
            int(_last_summary["documents_checked"])
            if _last_summary and "documents_checked" in _last_summary
            else None
        ),
        last_suspended_count=(
            int(_last_summary["suspended_provider_ids"])
            if _last_summary and "suspended_provider_ids" in _last_summary
            else None
        ),
    )


def run_compliance_monitor_tick(db: Session) -> dict:
    global _last_run_at, _last_summary
    if not settings.COMPLIANCE_MONITOR_WORKER_ENABLED:
        return {"skipped": True, "reason": "compliance_monitor_worker_disabled"}

    result = run_compliance_monitor(db)
    _last_run_at = datetime.now(timezone.utc)
    _last_summary = {
        "documents_checked": result["documents_checked"],
        "expiring_alerts": len(result["expiring_alerts"]),
        "suspended_provider_ids": len(result["suspended_provider_ids"]),
    }
    log_ops_event(
        db,
        event_type="COMPLIANCE_MONITOR_TICK",
        actor="compliance_scheduler",
        entity_type="system",
        entity_id=None,
        summary=(
            f"Compliance monitor checked {result['documents_checked']} document(s); "
            f"{len(result['suspended_provider_ids'])} provider(s) suspended"
        ),
        metadata=_last_summary,
        commit=True,
    )
    logger.info(
        "Compliance monitor tick: documents=%s expiring_alerts=%s suspended=%s",
        result["documents_checked"],
        len(result["expiring_alerts"]),
        len(result["suspended_provider_ids"]),
    )
    return result


async def _compliance_monitor_loop(stop_event: asyncio.Event) -> None:
    interval = max(300, settings.COMPLIANCE_MONITOR_WORKER_INTERVAL_SECONDS)
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            run_compliance_monitor_tick(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Compliance monitor tick failed: %s", exc)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue


async def start_compliance_scheduler() -> asyncio.Event | None:
    global _stop_event, _task
    if not settings.COMPLIANCE_MONITOR_WORKER_ENABLED:
        return None
    if _task is not None and not _task.done():
        return _stop_event

    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_compliance_monitor_loop(_stop_event))
    logger.info(
        "Compliance monitor worker started (interval=%ss)",
        settings.COMPLIANCE_MONITOR_WORKER_INTERVAL_SECONDS,
    )
    return _stop_event


async def stop_compliance_scheduler(stop_event: asyncio.Event | None) -> None:
    global _stop_event, _task
    if stop_event is not None:
        stop_event.set()
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    _stop_event = None
    logger.info("Compliance monitor worker stopped.")
