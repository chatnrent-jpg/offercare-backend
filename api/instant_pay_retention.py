"""Instant Pay retention — Stripe instant payouts after supervisor timesheet sign-off."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import MarylandProvider, ProviderStripePayoutAccount, ShiftTimesheetPayout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pay", tags=["instant-pay"])

_worker_stop_event: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


class SupervisorSignoffIn(BaseModel):
    timesheet_id: UUID
    provider_id: UUID
    gross_pay_amount: Decimal = Field(..., gt=0)
    supervisor_name: str = Field(..., min_length=2, max_length=255)
    supervisor_signature_token: str = Field(..., min_length=8, max_length=256)


class SupervisorSignoffResponse(BaseModel):
    ok: bool = True
    payout_id: str
    timesheet_id: str
    provider_id: str
    gross_pay_amount: float
    payout_status: str
    payout_eligible_at_utc: str
    instant_pay_window_minutes: int


class ProcessPayoutsResponse(BaseModel):
    ok: bool = True
    processed: int
    paid: int
    failed: int
    results: list[dict]


class RegisterStripeAccountIn(BaseModel):
    provider_id: UUID
    stripe_connect_account_id: str = Field(..., min_length=3, max_length=128)
    stripe_debit_card_id: str = Field(..., min_length=3, max_length=128)
    instant_payout_enabled: bool = True


@dataclass(frozen=True)
class InstantPayWorkerStatus:
    enabled: bool
    interval_seconds: int
    window_minutes: int
    running: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _eligible_at(signed_at: datetime) -> datetime:
    minutes = int(settings.INSTANT_PAY_WINDOW_MINUTES)
    return signed_at + timedelta(minutes=minutes)


def record_supervisor_signoff(db: Session, payload: SupervisorSignoffIn) -> ShiftTimesheetPayout:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == payload.provider_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="provider_not_found")

    existing = (
        db.query(ShiftTimesheetPayout)
        .filter(ShiftTimesheetPayout.timesheet_id == payload.timesheet_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="timesheet_payout_already_recorded")

    signed_at = _utc_now()
    payout = ShiftTimesheetPayout(
        payout_id=uuid4(),
        timesheet_id=payload.timesheet_id,
        provider_id=payload.provider_id,
        gross_pay_amount=payload.gross_pay_amount,
        supervisor_name=payload.supervisor_name.strip(),
        supervisor_signed_at=signed_at,
        payout_eligible_at=_eligible_at(signed_at),
        payout_status="PENDING",
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    logger.info(
        "Supervisor sign-off recorded payout=%s provider=%s eligible_at=%s",
        payout.payout_id,
        payout.provider_id,
        payout.payout_eligible_at,
    )
    return payout


def register_stripe_payout_account(db: Session, payload: RegisterStripeAccountIn) -> ProviderStripePayoutAccount:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == payload.provider_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="provider_not_found")

    row = db.query(ProviderStripePayoutAccount).filter(
        ProviderStripePayoutAccount.provider_id == payload.provider_id
    ).first()
    if row is None:
        row = ProviderStripePayoutAccount(
            provider_id=payload.provider_id,
            stripe_connect_account_id=payload.stripe_connect_account_id.strip(),
            stripe_debit_card_id=payload.stripe_debit_card_id.strip(),
            instant_payout_enabled=payload.instant_payout_enabled,
        )
        db.add(row)
    else:
        row.stripe_connect_account_id = payload.stripe_connect_account_id.strip()
        row.stripe_debit_card_id = payload.stripe_debit_card_id.strip()
        row.instant_payout_enabled = payload.instant_payout_enabled
        row.updated_at = _utc_now()
    db.commit()
    db.refresh(row)
    return row


def _execute_stripe_instant_payout(
    *,
    amount_cents: int,
    connect_account_id: str,
    debit_card_id: str,
) -> tuple[str, str]:
    if settings.STRIPE_INSTANT_PAYOUT_DRY_RUN:
        return "DRY_RUN", f"dry_run_payout_{amount_cents}"

    secret = str(settings.STRIPE_SECRET_KEY or "").strip()
    if not secret:
        raise RuntimeError("stripe_secret_key_not_configured")

    import stripe

    stripe.api_key = secret
    payout = stripe.Payout.create(
        amount=amount_cents,
        currency="usd",
        method="instant",
        destination=debit_card_id,
        stripe_account=connect_account_id,
    )
    return "STRIPE", str(payout.id)


def process_due_instant_payouts(db: Session) -> ProcessPayoutsResponse:
    now = _utc_now()
    due_rows = (
        db.query(ShiftTimesheetPayout)
        .filter(ShiftTimesheetPayout.payout_status == "PENDING")
        .filter(ShiftTimesheetPayout.payout_eligible_at <= now)
        .order_by(ShiftTimesheetPayout.payout_eligible_at.asc())
        .limit(50)
        .all()
    )

    paid = 0
    failed = 0
    results: list[dict] = []

    for payout in due_rows:
        payout.payout_status = "PROCESSING"
        db.flush()

        account = (
            db.query(ProviderStripePayoutAccount)
            .filter(ProviderStripePayoutAccount.provider_id == payout.provider_id)
            .first()
        )
        if account is None or not account.instant_payout_enabled:
            payout.payout_status = "FAILED"
            payout.failure_reason = "stripe_payout_account_missing"
            failed += 1
            results.append(
                {
                    "payout_id": str(payout.payout_id),
                    "status": payout.payout_status,
                    "reason": payout.failure_reason,
                }
            )
            continue

        amount_cents = int(Decimal(payout.gross_pay_amount) * 100)
        if amount_cents <= 0:
            payout.payout_status = "FAILED"
            payout.failure_reason = "invalid_payout_amount"
            failed += 1
            results.append(
                {
                    "payout_id": str(payout.payout_id),
                    "status": payout.payout_status,
                    "reason": payout.failure_reason,
                }
            )
            continue

        try:
            mode, stripe_payout_id = _execute_stripe_instant_payout(
                amount_cents=amount_cents,
                connect_account_id=account.stripe_connect_account_id,
                debit_card_id=account.stripe_debit_card_id,
            )
            payout.payout_status = "PAID"
            payout.stripe_mode = mode
            payout.stripe_payout_id = stripe_payout_id
            payout.paid_at = _utc_now()
            payout.failure_reason = None
            paid += 1
            results.append(
                {
                    "payout_id": str(payout.payout_id),
                    "status": "PAID",
                    "stripe_payout_id": stripe_payout_id,
                    "amount_cents": amount_cents,
                    "mode": mode,
                }
            )
        except Exception as exc:  # noqa: BLE001
            payout.payout_status = "FAILED"
            payout.failure_reason = str(exc)[:500]
            failed += 1
            logger.warning("Instant payout failed payout=%s error=%s", payout.payout_id, exc)
            results.append(
                {
                    "payout_id": str(payout.payout_id),
                    "status": "FAILED",
                    "reason": payout.failure_reason,
                }
            )

    db.commit()
    return ProcessPayoutsResponse(
        ok=True,
        processed=len(due_rows),
        paid=paid,
        failed=failed,
        results=results,
    )


def instant_pay_worker_status() -> InstantPayWorkerStatus:
    return InstantPayWorkerStatus(
        enabled=settings.INSTANT_PAY_WORKER_ENABLED,
        interval_seconds=settings.INSTANT_PAY_WORKER_INTERVAL_SECONDS,
        window_minutes=settings.INSTANT_PAY_WINDOW_MINUTES,
        running=_worker_task is not None and not _worker_task.done(),
    )


def run_instant_pay_worker_tick(db: Session) -> ProcessPayoutsResponse:
    if not settings.INSTANT_PAY_WORKER_ENABLED:
        return ProcessPayoutsResponse(ok=True, processed=0, paid=0, failed=0, results=[])
    return process_due_instant_payouts(db)


async def _instant_pay_worker_loop(stop_event: asyncio.Event) -> None:
    interval = max(15, int(settings.INSTANT_PAY_WORKER_INTERVAL_SECONDS))
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            run_instant_pay_worker_tick(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Instant pay worker tick failed: %s", exc)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue


async def start_instant_pay_worker() -> asyncio.Event | None:
    global _worker_stop_event, _worker_task
    if not settings.INSTANT_PAY_WORKER_ENABLED:
        return None
    if _worker_task is not None and not _worker_task.done():
        return _worker_stop_event
    _worker_stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_instant_pay_worker_loop(_worker_stop_event))
    logger.info(
        "Instant pay worker started (interval=%ss, window=%sm)",
        settings.INSTANT_PAY_WORKER_INTERVAL_SECONDS,
        settings.INSTANT_PAY_WINDOW_MINUTES,
    )
    return _worker_stop_event


async def stop_instant_pay_worker(stop_event: asyncio.Event | None) -> None:
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


@router.post("/timesheet/supervisor-signoff", response_model=SupervisorSignoffResponse)
def supervisor_timesheet_signoff(payload: SupervisorSignoffIn, db: Session = Depends(get_db)) -> SupervisorSignoffResponse:
    payout = record_supervisor_signoff(db, payload)
    return SupervisorSignoffResponse(
        ok=True,
        payout_id=str(payout.payout_id),
        timesheet_id=str(payout.timesheet_id),
        provider_id=str(payout.provider_id),
        gross_pay_amount=float(payout.gross_pay_amount),
        payout_status=payout.payout_status,
        payout_eligible_at_utc=payout.payout_eligible_at.isoformat(),
        instant_pay_window_minutes=int(settings.INSTANT_PAY_WINDOW_MINUTES),
    )


@router.post(
    "/register-stripe-account",
    dependencies=[Depends(require_admin_api_key)],
)
def register_provider_stripe_account(payload: RegisterStripeAccountIn, db: Session = Depends(get_db)) -> dict:
    row = register_stripe_payout_account(db, payload)
    return {
        "ok": True,
        "provider_id": str(row.provider_id),
        "stripe_connect_account_id": row.stripe_connect_account_id,
        "instant_payout_enabled": row.instant_payout_enabled,
    }


@router.post(
    "/process-due-payouts",
    response_model=ProcessPayoutsResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def process_due_payouts(db: Session = Depends(get_db)) -> ProcessPayoutsResponse:
    return process_due_instant_payouts(db)


def register_instant_pay_retention(app) -> None:
    app.include_router(router)
