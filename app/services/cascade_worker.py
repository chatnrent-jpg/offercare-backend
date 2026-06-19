"""Background cascade worker — auto-notify next clinician after timeout."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import OfferCareJobOffer
from app.services.shift_cascade import CascadeAdvanceResult, advance_cascade, get_cascade_status

logger = logging.getLogger(__name__)

_worker_stop_event: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


@dataclass(frozen=True)
class CascadeWorkerStatus:
    enabled: bool
    cascade_enabled: bool
    interval_seconds: int
    timeout_seconds: int
    running: bool


def cascade_worker_status() -> CascadeWorkerStatus:
    return CascadeWorkerStatus(
        enabled=settings.SNIPER_CASCADE_WORKER_ENABLED,
        cascade_enabled=settings.SNIPER_CASCADE_ENABLED,
        interval_seconds=settings.SNIPER_CASCADE_WORKER_INTERVAL_SECONDS,
        timeout_seconds=settings.SNIPER_CASCADE_TIMEOUT_SECONDS,
        running=_worker_task is not None and not _worker_task.done(),
    )


def run_cascade_worker_tick(db: Session) -> list[CascadeAdvanceResult]:
    if not settings.SNIPER_CASCADE_WORKER_ENABLED or not settings.SNIPER_CASCADE_ENABLED:
        return []

    offers = (
        db.query(OfferCareJobOffer)
        .filter(
            OfferCareJobOffer.compliance_lock_status == "BROADCASTING",
            OfferCareJobOffer.broadcast_wave_id.isnot(None),
        )
        .all()
    )
    results: list[CascadeAdvanceResult] = []
    for offer in offers:
        cascade = get_cascade_status(db, offer.offer_id)
        if not cascade.can_advance:
            continue
        result = advance_cascade(db, offer.offer_id, force=False, actor="cascade_worker")
        if result.status == "advanced":
            results.append(result)
            logger.info(
                "Cascade worker notified %s for offer %s",
                result.delivery.phone_number if result.delivery else "clinician",
                offer.offer_id,
            )
    return results


async def _cascade_worker_loop(stop_event: asyncio.Event) -> None:
    interval = max(1, settings.SNIPER_CASCADE_WORKER_INTERVAL_SECONDS)
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            run_cascade_worker_tick(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cascade worker tick failed: %s", exc)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue


async def start_cascade_worker() -> asyncio.Event | None:
    global _worker_stop_event, _worker_task
    if not settings.SNIPER_CASCADE_WORKER_ENABLED:
        return None
    if _worker_task is not None and not _worker_task.done():
        return _worker_stop_event
    _worker_stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_cascade_worker_loop(_worker_stop_event))
    logger.info(
        "Cascade worker started (interval=%ss, timeout=%ss)",
        settings.SNIPER_CASCADE_WORKER_INTERVAL_SECONDS,
        settings.SNIPER_CASCADE_TIMEOUT_SECONDS,
    )
    return _worker_stop_event


async def stop_cascade_worker(stop_event: asyncio.Event | None) -> None:
    global _worker_task, _worker_stop_event
    if stop_event is not None:
        stop_event.set()
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    _worker_stop_event = None
    logger.info("Cascade worker stopped.")
