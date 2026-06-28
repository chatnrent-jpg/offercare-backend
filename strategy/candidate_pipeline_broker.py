"""Candidate pipeline broker — frictionless velocity metrics over match → Stripe escrow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_RECENT_LIMIT = 50
_NIGHT_HOUR_START = 18
_NIGHT_HOUR_END = 7
_INSTANT_PAY_WINDOW_MINUTES_DEFAULT = 30

_PIPELINE_VELOCITY_SQL = text(
    """
    SELECT
        o.offer_id::text AS offer_id,
        o.shift_role,
        o.created_at AS requested_at,
        o.shift_starts_at,
        p.placement_id::text AS placement_id,
        p.compliance_snapshot_token AS timesheet_token,
        p.outbound_payload_timestamp AS matched_at,
        p.assigned_clinician_id::text AS provider_id,
        mp.full_name AS provider_name,
        spa.updated_at AS stripe_account_at,
        stp.created_at AS timesheet_payout_at,
        stp.payout_status,
        stp.paid_at,
        stp.payout_eligible_at,
        ios.start_time AS ingested_start_time
    FROM offercare_job_offers o
    INNER JOIN clinical_placements_ledger p
        ON p.offer_id = o.offer_id
    INNER JOIN maryland_providers mp
        ON mp.provider_id = p.assigned_clinician_id
    LEFT JOIN provider_stripe_payout_accounts spa
        ON spa.provider_id = p.assigned_clinician_id
    LEFT JOIN LATERAL (
        SELECT
            stp_inner.created_at,
            stp_inner.payout_status,
            stp_inner.paid_at,
            stp_inner.payout_eligible_at
        FROM shift_timesheet_payouts stp_inner
        WHERE stp_inner.provider_id = p.assigned_clinician_id
          AND stp_inner.created_at >= p.outbound_payload_timestamp
        ORDER BY stp_inner.created_at ASC
        LIMIT 1
    ) stp ON TRUE
    LEFT JOIN ingested_open_shifts ios
        ON ios.offer_id = o.offer_id
    WHERE o.assigned_provider_id IS NOT NULL
      AND upper(o.shift_role) LIKE '%CNA%'
    ORDER BY p.outbound_payload_timestamp DESC
    LIMIT :limit
    """
)


class PipelineBrokerLoopException(RuntimeError):
    """Hive supervisor halt — broker compile/DB reference failure."""


@dataclass(frozen=True)
class PipelineVelocityRecord:
    offer_id: str
    provider_id: str
    provider_name: str
    timesheet_token: str
    requested_at: datetime
    matched_at: datetime
    stripe_escrow_initialized_at: datetime
    frictionless_velocity_seconds: float
    payout_status: str | None = None
    cleared_payout_loop: bool = False


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_hour_token(value: str | None) -> int | None:
    token = str(value or "").strip()
    if not token:
        return None
    head = token.split(":")[0]
    try:
        return int(head)
    except ValueError:
        return None


def _is_night_shift_cna(
    shift_role: str,
    shift_starts_at: datetime | None,
    ingested_start_time: str | None,
) -> bool:
    role = str(shift_role or "").upper()
    if "CNA" not in role and role not in {"GNA"}:
        return False
    if "NIGHT" in role or "OVERNIGHT" in role:
        return True
    for candidate in (shift_starts_at,):
        if candidate is not None:
            hour = _utc(candidate).hour
            if hour >= _NIGHT_HOUR_START or hour < _NIGHT_HOUR_END:
                return True
    ingested_hour = _parse_hour_token(ingested_start_time)
    if ingested_hour is not None and (ingested_hour >= _NIGHT_HOUR_START or ingested_hour < _NIGHT_HOUR_END):
        return True
    return False


def _stripe_escrow_timestamp(row: dict[str, Any]) -> datetime | None:
    for key in ("stripe_account_at", "timesheet_payout_at"):
        value = row.get(key)
        if value is not None:
            return _utc(value)
    return None


def _cleared_payout_loop(
    row: dict[str, Any],
    *,
    window_minutes: int,
) -> bool:
    status = str(row.get("payout_status") or "").upper()
    if status != "PAID":
        return False
    paid_at = row.get("paid_at")
    eligible_at = row.get("payout_eligible_at")
    matched_at = row.get("matched_at")
    if paid_at is None or eligible_at is None or matched_at is None:
        return False
    paid_ts = _utc(paid_at)
    eligible_ts = _utc(eligible_at)
    matched_ts = _utc(matched_at)
    if paid_ts > eligible_ts:
        return False
    loop_seconds = (eligible_ts - matched_ts).total_seconds()
    return loop_seconds <= float(window_minutes * 60)


class CandidatePipelineBroker:
    """Real-time candidate acquisition velocity broker over match + Stripe escrow events."""

    def __init__(self, db: Session | None = None, *, recent_limit: int = _DEFAULT_RECENT_LIMIT) -> None:
        if recent_limit <= 0:
            raise ValueError("recent_limit must be positive")
        self._db = db
        self._owns_session = False
        self.recent_limit = int(recent_limit)
        self._cached_instant_pay_window_minutes: int | None = None
        self._stripe_configured: bool | None = None

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise PipelineBrokerLoopException("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _instant_pay_window_minutes(self) -> int:
        if self._cached_instant_pay_window_minutes is None:
            try:
                from app.config import settings

                self._cached_instant_pay_window_minutes = int(
                    getattr(settings, "INSTANT_PAY_WINDOW_MINUTES", _INSTANT_PAY_WINDOW_MINUTES_DEFAULT)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Instant pay settings unavailable; using default window: %s", exc)
                self._cached_instant_pay_window_minutes = _INSTANT_PAY_WINDOW_MINUTES_DEFAULT
        return self._cached_instant_pay_window_minutes

    def _stripe_dependencies_ready(self) -> bool:
        if self._stripe_configured is None:
            try:
                from app.config import settings

                dry_run = bool(getattr(settings, "STRIPE_INSTANT_PAYOUT_DRY_RUN", True))
                secret = str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
                self._stripe_configured = dry_run or bool(secret)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Stripe settings unavailable; treating as dry-run ready: %s", exc)
                self._stripe_configured = True
        return self._stripe_configured

    def _fetch_matching_rows(self) -> list[dict[str, Any]]:
        try:
            result = self.db.execute(_PIPELINE_VELOCITY_SQL, {"limit": self.recent_limit})
            return [dict(row._mapping) for row in result]
        except SQLAlchemyError as exc:
            raise PipelineBrokerLoopException("database_reference_failed") from exc

    def get_pipeline_velocity(self) -> list[PipelineVelocityRecord]:
        """Frictionless velocity: seconds from night-shift CNA request to Stripe escrow hook."""
        self._stripe_dependencies_ready()
        window_minutes = self._instant_pay_window_minutes()
        records: list[PipelineVelocityRecord] = []

        for row in self._fetch_matching_rows():
            if not _is_night_shift_cna(
                str(row.get("shift_role") or ""),
                row.get("shift_starts_at"),
                row.get("ingested_start_time"),
            ):
                continue

            requested_at = row.get("requested_at")
            matched_at = row.get("matched_at")
            escrow_at = _stripe_escrow_timestamp(row)
            if requested_at is None or matched_at is None or escrow_at is None:
                continue

            requested_ts = _utc(requested_at)
            matched_ts = _utc(matched_at)
            velocity_seconds = max((escrow_at - requested_ts).total_seconds(), 0.0)

            records.append(
                PipelineVelocityRecord(
                    offer_id=str(row.get("offer_id") or ""),
                    provider_id=str(row.get("provider_id") or ""),
                    provider_name=str(row.get("provider_name") or ""),
                    timesheet_token=str(row.get("timesheet_token") or ""),
                    requested_at=requested_ts,
                    matched_at=matched_ts,
                    stripe_escrow_initialized_at=escrow_at,
                    frictionless_velocity_seconds=round(velocity_seconds, 3),
                    payout_status=str(row.get("payout_status") or "") or None,
                    cleared_payout_loop=_cleared_payout_loop(row, window_minutes=window_minutes),
                )
            )

        return records

    def fetch_dashboard_payload(self) -> dict[str, Any]:
        """Dense dashboard payload for candidate acquisition velocity."""
        velocity_records = self.get_pipeline_velocity()
        all_rows = self._fetch_matching_rows()
        window_minutes = self._instant_pay_window_minutes()

        night_rows = [
            row
            for row in all_rows
            if _is_night_shift_cna(
                str(row.get("shift_role") or ""),
                row.get("shift_starts_at"),
                row.get("ingested_start_time"),
            )
        ]

        velocity_values = [record.frictionless_velocity_seconds for record in velocity_records]
        average_match_time_seconds = (
            round(sum(velocity_values) / len(velocity_values), 3) if velocity_values else 0.0
        )

        total_automated_dispatches = sum(
            1
            for row in night_rows
            if row.get("matched_at") is not None and str(row.get("timesheet_token") or "").strip()
        )

        stripe_ready_rows = [row for row in night_rows if _stripe_escrow_timestamp(row) is not None]
        cleared_rows = [
            row
            for row in stripe_ready_rows
            if _cleared_payout_loop(row, window_minutes=window_minutes)
        ]
        stripe_conversion_rate = (
            round((len(cleared_rows) / len(stripe_ready_rows)) * 100.0, 2)
            if stripe_ready_rows
            else 0.0
        )

        return {
            "ok": True,
            "average_match_time_seconds": average_match_time_seconds,
            "total_automated_dispatches": int(total_automated_dispatches),
            "stripe_conversion_rate": stripe_conversion_rate,
            "sample_count": len(velocity_records),
            "instant_pay_window_minutes": window_minutes,
            "recent_velocity_records": [
                {
                    "offer_id": record.offer_id,
                    "provider_id": record.provider_id,
                    "provider_name": record.provider_name,
                    "timesheet_token": record.timesheet_token,
                    "frictionless_velocity_seconds": record.frictionless_velocity_seconds,
                    "cleared_payout_loop": record.cleared_payout_loop,
                }
                for record in velocity_records
            ],
        }


if __name__ == "__main__":
    print("COMPILE_OK candidate_pipeline_broker")
    broker = CandidatePipelineBroker(db=None)
    print(f"broker={broker.__class__.__name__} recent_limit={broker.recent_limit}")
