"""Background staffing scheduler — VMS poll and daily job board crisis scans."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.crisis_indicator import scan_job_board_crisis_leads
from app.services.ops_metrics import log_ops_event
from app.services.vms_shift_ingestion import run_vms_ingestion

logger = logging.getLogger(__name__)

_stop_event: asyncio.Event | None = None
_vms_task: asyncio.Task | None = None
_job_board_task: asyncio.Task | None = None
_vms_last_run_at: datetime | None = None
_job_board_last_run_at: datetime | None = None
_vms_last_summary: dict | None = None
_job_board_last_summary: dict | None = None


@dataclass(frozen=True)
class StaffingSchedulerStatus:
    vms_enabled: bool
    vms_interval_seconds: int
    vms_running: bool
    vms_last_run_at: datetime | None
    job_board_enabled: bool
    job_board_interval_seconds: int
    job_board_running: bool
    job_board_last_run_at: datetime | None


def staffing_scheduler_status() -> StaffingSchedulerStatus:
    return StaffingSchedulerStatus(
        vms_enabled=settings.STAFFING_VMS_WORKER_ENABLED,
        vms_interval_seconds=settings.STAFFING_VMS_WORKER_INTERVAL_SECONDS,
        vms_running=_vms_task is not None and not _vms_task.done(),
        vms_last_run_at=_vms_last_run_at,
        job_board_enabled=settings.STAFFING_JOB_BOARD_WORKER_ENABLED,
        job_board_interval_seconds=settings.STAFFING_JOB_BOARD_WORKER_INTERVAL_SECONDS,
        job_board_running=_job_board_task is not None and not _job_board_task.done(),
        job_board_last_run_at=_job_board_last_run_at,
    )


def run_vms_worker_tick(db: Session) -> dict:
    global _vms_last_run_at, _vms_last_summary
    if not settings.STAFFING_VMS_WORKER_ENABLED:
        return {"skipped": True, "reason": "vms_worker_disabled"}

    result = run_vms_ingestion(db, persist=True)
    _vms_last_run_at = datetime.now(timezone.utc)
    _vms_last_summary = {
        "shifts_fetched": result["shifts_fetched"],
        "offers_created": result["offers_created"],
        "offers_skipped": result["offers_skipped"],
    }
    log_ops_event(
        db,
        event_type="VMS_WORKER_TICK",
        actor="staffing_scheduler",
        entity_type="system",
        entity_id=None,
        summary=(
            f"VMS worker polled {result['shifts_fetched']} shift(s); "
            f"created {result['offers_created']} offer(s)"
        ),
        metadata=_vms_last_summary,
        commit=True,
    )
    logger.info(
        "VMS worker tick: fetched=%s created=%s skipped=%s",
        result["shifts_fetched"],
        result["offers_created"],
        result["offers_skipped"],
    )
    return result


def run_job_board_worker_tick(db: Session) -> dict:
    global _job_board_last_run_at, _job_board_last_summary
    if not settings.STAFFING_JOB_BOARD_WORKER_ENABLED:
        return {"skipped": True, "reason": "job_board_worker_disabled"}

    result = scan_job_board_crisis_leads(db)
    _job_board_last_run_at = datetime.now(timezone.utc)
    _job_board_last_summary = {
        "listings_scraped": result["listings_scraped"],
        "crisis_listings": result["crisis_listings"],
        "signals_created": result["signals_created"],
    }
    log_ops_event(
        db,
        event_type="JOB_BOARD_WORKER_TICK",
        actor="staffing_scheduler",
        entity_type="system",
        entity_id=None,
        summary=(
            f"Job board worker scraped {result['listings_scraped']} listing(s); "
            f"{result['crisis_listings']} crisis lead(s)"
        ),
        metadata=_job_board_last_summary,
        commit=True,
    )
    logger.info(
        "Job board worker tick: scraped=%s crisis=%s signals=%s",
        result["listings_scraped"],
        result["crisis_listings"],
        result["signals_created"],
    )
    return result


async def _vms_worker_loop(stop_event: asyncio.Event) -> None:
    interval = max(60, settings.STAFFING_VMS_WORKER_INTERVAL_SECONDS)
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            run_vms_worker_tick(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("VMS worker tick failed: %s", exc)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue


async def _job_board_worker_loop(stop_event: asyncio.Event) -> None:
    interval = max(300, settings.STAFFING_JOB_BOARD_WORKER_INTERVAL_SECONDS)
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            run_job_board_worker_tick(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Job board worker tick failed: %s", exc)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue


async def start_staffing_scheduler() -> asyncio.Event | None:
    global _stop_event, _vms_task, _job_board_task
    if not settings.STAFFING_VMS_WORKER_ENABLED and not settings.STAFFING_JOB_BOARD_WORKER_ENABLED:
        return None
    if (_vms_task is not None and not _vms_task.done()) or (
        _job_board_task is not None and not _job_board_task.done()
    ):
        return _stop_event

    _stop_event = asyncio.Event()
    if settings.STAFFING_VMS_WORKER_ENABLED:
        _vms_task = asyncio.create_task(_vms_worker_loop(_stop_event))
        logger.info(
            "VMS staffing worker started (interval=%ss)",
            settings.STAFFING_VMS_WORKER_INTERVAL_SECONDS,
        )
    if settings.STAFFING_JOB_BOARD_WORKER_ENABLED:
        _job_board_task = asyncio.create_task(_job_board_worker_loop(_stop_event))
        logger.info(
            "Job board staffing worker started (interval=%ss)",
            settings.STAFFING_JOB_BOARD_WORKER_INTERVAL_SECONDS,
        )
    return _stop_event


async def stop_staffing_scheduler(stop_event: asyncio.Event | None) -> None:
    global _stop_event, _vms_task, _job_board_task
    if stop_event is not None:
        stop_event.set()
    for task in (_vms_task, _job_board_task):
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _vms_task = None
    _job_board_task = None
    _stop_event = None
    logger.info("Staffing scheduler stopped.")
