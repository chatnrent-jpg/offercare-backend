"""Match retry scheduler — semantic fallback cascade for unfilled shift demands."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_RECENT_LIMIT = 50
_DEFAULT_RETRY_TIMEOUT_SECONDS = 300
_NIGHT_HOUR_START = 18
_NIGHT_HOUR_END = 7
_UNFILLED_DISPATCH_STATUSES = ("UNFILLED", "PENDING_DISPATCH", "BROADCASTING")
_DEFAULT_CRITICAL_CARE_TAGS = ("dementia", "memory", "night", "behavioral", "gna")


class MatchRetrySchedulerHardStop(RuntimeError):
    """Hive halt — match retry scheduler compile/DB failure."""


@dataclass(frozen=True)
class UnfilledDemandRecord:
    offer_id: str
    shift_role: str
    compliance_lock_status: str
    created_at: datetime
    shift_starts_at: datetime | None
    facility_id: str | None
    care_tags: tuple[str, ...]
    retry_attempt_count: int
    last_broadcast_at: datetime | None


@dataclass(frozen=True)
class RetryCascadeResult:
    offer_id: str
    status: str
    retry_attempt_count: int
    selected_rank: int | None
    provider_id: str | None
    provider_name: str | None
    message: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_night_shift(shift_role: str, shift_starts_at: datetime | None, start_time: str | None = None) -> bool:
    role = str(shift_role or "").upper()
    if "NIGHT" in role or "OVERNIGHT" in role:
        return True
    if shift_starts_at is not None:
        hour = _utc(shift_starts_at).hour
        if hour >= _NIGHT_HOUR_START or hour < _NIGHT_HOUR_END:
            return True
    if start_time:
        head = str(start_time).split(":")[0]
        try:
            hour = int(head)
            return hour >= _NIGHT_HOUR_START or hour < _NIGHT_HOUR_END
        except ValueError:
            return False
    return False


def _extract_care_tags(*texts: str | None) -> tuple[str, ...]:
    blob = " ".join(str(text or "") for text in texts).lower()
    tags = tuple(tag for tag in _DEFAULT_CRITICAL_CARE_TAGS if tag in blob)
    return tags


def _parse_retry_meta(raw: str | None) -> dict[str, Any]:
    token = str(raw or "").strip()
    if not token:
        return {"retry_attempt_count": 0, "messaged_provider_ids": []}
    try:
        payload = json.loads(token)
        if isinstance(payload, dict):
            payload.setdefault("retry_attempt_count", 0)
            payload.setdefault("messaged_provider_ids", [])
            return payload
    except json.JSONDecodeError:
        pass
    return {"retry_attempt_count": 0, "messaged_provider_ids": []}


class MatchRetryScheduler:
    """Resiliency pipeline — cycles semantic fallback candidates for unfilled shifts."""

    def __init__(
        self,
        db: Session | None = None,
        *,
        recent_limit: int = _DEFAULT_RECENT_LIMIT,
        retry_timeout_seconds: int = _DEFAULT_RETRY_TIMEOUT_SECONDS,
        critical_care_tags: tuple[str, ...] | None = None,
    ) -> None:
        if recent_limit <= 0:
            raise ValueError("recent_limit must be positive")
        if retry_timeout_seconds <= 0:
            raise ValueError("retry_timeout_seconds must be positive")
        self._db = db
        self._owns_session = False
        self.recent_limit = int(recent_limit)
        self.retry_timeout_seconds = int(retry_timeout_seconds)
        self.critical_care_tags = tuple(critical_care_tags or _DEFAULT_CRITICAL_CARE_TAGS)
        self._semantic_engine: Any | None = None

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise MatchRetrySchedulerHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _semantic_payout_engine(self) -> Any:
        if self._semantic_engine is None:
            try:
                from strategy.semantic_payout_engine import SemanticPayoutEngine
            except Exception as exc:  # noqa: BLE001
                raise MatchRetrySchedulerHardStop("semantic_payout_engine_import_failed") from exc
            self._semantic_engine = SemanticPayoutEngine(prefer_live_db=True)
        return self._semantic_engine

    def _messaged_provider_ids(self, offer_id: UUID) -> set[str]:
        from app.models import ShiftNotificationLog

        rows = (
            self.db.query(ShiftNotificationLog.provider_id)
            .filter(ShiftNotificationLog.offer_id == offer_id)
            .all()
        )
        return {str(row[0]) for row in rows}

    def _last_broadcast_at(self, offer_id: UUID, offer_created_at: datetime | None) -> datetime:
        from app.models import ShiftNotificationLog

        row = (
            self.db.query(ShiftNotificationLog.sent_at)
            .filter(ShiftNotificationLog.offer_id == offer_id)
            .order_by(ShiftNotificationLog.sent_at.desc())
            .first()
        )
        if row and row[0] is not None:
            return _utc(row[0])
        if offer_created_at is not None:
            return _utc(offer_created_at)
        return _utc_now()

    def _ledger_retry_meta(self, offer_id: UUID) -> dict[str, Any]:
        from app.models import ClinicalPlacementLedger, IngestedOpenShift

        placement = (
            self.db.query(ClinicalPlacementLedger)
            .filter(ClinicalPlacementLedger.offer_id == offer_id)
            .order_by(ClinicalPlacementLedger.outbound_payload_timestamp.desc())
            .first()
        )
        if placement is not None and placement.vms_external_ref:
            return _parse_retry_meta(placement.vms_external_ref)

        ingest = (
            self.db.query(IngestedOpenShift)
            .filter(IngestedOpenShift.offer_id == offer_id)
            .order_by(IngestedOpenShift.ingested_at.desc())
            .first()
        )
        if ingest is not None and ingest.match_payload_json:
            return _parse_retry_meta(ingest.match_payload_json)
        return {"retry_attempt_count": 0, "messaged_provider_ids": []}

    def _persist_retry_meta(self, offer_id: UUID, meta: dict[str, Any]) -> None:
        from app.models import ClinicalPlacementLedger, IngestedOpenShift

        encoded = json.dumps(meta, separators=(",", ":"), sort_keys=True)
        placement = (
            self.db.query(ClinicalPlacementLedger)
            .filter(ClinicalPlacementLedger.offer_id == offer_id)
            .order_by(ClinicalPlacementLedger.outbound_payload_timestamp.desc())
            .first()
        )
        if placement is not None:
            placement.vms_external_ref = encoded[:100]
        ingest = (
            self.db.query(IngestedOpenShift)
            .filter(IngestedOpenShift.offer_id == offer_id)
            .order_by(IngestedOpenShift.ingested_at.desc())
            .first()
        )
        if ingest is not None:
            ingest.match_payload_json = encoded
        self.db.commit()

    def scan_unfilled_demands(self) -> list[UnfilledDemandRecord]:
        """Scan recent unfilled / pending-dispatch offers with critical night-shift tags."""
        try:
            from app.models import IngestedOpenShift, OfferCareJobOffer

            rows = (
                self.db.query(OfferCareJobOffer, IngestedOpenShift)
                .outerjoin(IngestedOpenShift, IngestedOpenShift.offer_id == OfferCareJobOffer.offer_id)
                .filter(
                    OfferCareJobOffer.assigned_provider_id.is_(None),
                    or_(
                        OfferCareJobOffer.compliance_lock_status.in_(_UNFILLED_DISPATCH_STATUSES),
                        OfferCareJobOffer.compliance_lock_status.is_(None),
                    ),
                )
                .order_by(OfferCareJobOffer.created_at.desc())
                .limit(self.recent_limit)
                .all()
            )
        except SQLAlchemyError as exc:
            raise MatchRetrySchedulerHardStop("database_reference_failed") from exc

        demands: list[UnfilledDemandRecord] = []
        for offer, ingest in rows:
            if not _is_night_shift(
                str(offer.shift_role or ""),
                offer.shift_starts_at,
                str(ingest.start_time) if ingest is not None else None,
            ):
                continue

            care_tags = _extract_care_tags(
                offer.shift_role,
                ingest.unit_dept if ingest is not None else None,
                ingest.payload_json if ingest is not None else None,
            )
            if self.critical_care_tags and not any(tag in care_tags for tag in self.critical_care_tags):
                continue

            retry_meta = self._ledger_retry_meta(offer.offer_id)
            demands.append(
                UnfilledDemandRecord(
                    offer_id=str(offer.offer_id),
                    shift_role=str(offer.shift_role or ""),
                    compliance_lock_status=str(offer.compliance_lock_status or "BROADCASTING"),
                    created_at=_utc(offer.created_at) if offer.created_at else _utc_now(),
                    shift_starts_at=_utc(offer.shift_starts_at) if offer.shift_starts_at else None,
                    facility_id=str(offer.facility_id) if offer.facility_id else None,
                    care_tags=care_tags,
                    retry_attempt_count=int(retry_meta.get("retry_attempt_count") or 0),
                    last_broadcast_at=self._last_broadcast_at(
                        offer.offer_id,
                        offer.created_at,
                    ),
                )
            )
        return demands

    def _build_semantic_query(self, demand: UnfilledDemandRecord) -> str:
        tags = " ".join(demand.care_tags) if demand.care_tags else "night shift"
        return (
            f"{demand.shift_role} {tags} — unfilled facility demand retry "
            f"offer {demand.offer_id[:8]}"
        )

    def _build_shift_context(self, demand: UnfilledDemandRecord) -> dict[str, Any]:
        return {
            "required_role": "CNA" if "CNA" in demand.shift_role.upper() else demand.shift_role,
            "facility_type": "SNF",
            "shift_band": "night",
            "care_tags": list(demand.care_tags),
            "offer_id": demand.offer_id,
            "retry_attempt_count": demand.retry_attempt_count,
        }

    def _resolve_provider_uuid(self, provider_token: str) -> UUID | None:
        from app.models import MarylandProvider

        token = str(provider_token or "").strip()
        if not token:
            return None
        try:
            return UUID(token)
        except ValueError:
            pass
        row = (
            self.db.query(MarylandProvider.provider_id)
            .filter(MarylandProvider.md_license_number == token)
            .first()
        )
        return row[0] if row else None

    def _trigger_dispatch_hook(
        self,
        *,
        offer_id: UUID,
        provider_uuid: UUID,
        provider_label: str,
        selected_rank: int,
        retry_attempt_count: int,
        broadcast_wave_id: UUID | None,
    ) -> None:
        from app.models import ShiftNotificationLog

        message = (
            f"Semantic retry dispatch rank #{selected_rank} "
            f"attempt #{retry_attempt_count} -> {provider_label}"
        )
        self.db.add(
            ShiftNotificationLog(
                notification_id=uuid4(),
                offer_id=offer_id,
                provider_id=provider_uuid,
                channel="SMS",
                status="QUEUED",
                message_body=message[:1000],
                broadcast_wave_id=broadcast_wave_id,
            )
        )
        self.db.commit()

    def execute_retry_cascade(self) -> list[RetryCascadeResult]:
        """Advance semantic fallback candidates when broadcast timeout expires."""
        results: list[RetryCascadeResult] = []
        timeout_delta = timedelta(seconds=self.retry_timeout_seconds)
        engine = self._semantic_payout_engine()

        for demand in self.scan_unfilled_demands():
            elapsed = _utc_now() - demand.last_broadcast_at
            if elapsed < timeout_delta:
                results.append(
                    RetryCascadeResult(
                        offer_id=demand.offer_id,
                        status="waiting_timeout",
                        retry_attempt_count=demand.retry_attempt_count,
                        selected_rank=None,
                        provider_id=None,
                        provider_name=None,
                        message=f"Retry window active — {int(elapsed.total_seconds())}s elapsed",
                    )
                )
                continue

            query = self._build_semantic_query(demand)
            shift_context = self._build_shift_context(demand)
            try:
                vector_result = engine.find_top_vector_matches(
                    query,
                    top_k=max(5, demand.retry_attempt_count + 3),
                    shift_context=shift_context,
                )
            except ValueError as exc:
                results.append(
                    RetryCascadeResult(
                        offer_id=demand.offer_id,
                        status="sentinel_blocked",
                        retry_attempt_count=demand.retry_attempt_count,
                        selected_rank=None,
                        provider_id=None,
                        provider_name=None,
                        message=str(exc)[:240],
                    )
                )
                continue

            messaged_license_ids = self._messaged_provider_ids(UUID(demand.offer_id))
            retry_meta = self._ledger_retry_meta(UUID(demand.offer_id))
            messaged_tokens = {str(token) for token in retry_meta.get("messaged_provider_ids") or []}

            selected = None
            for candidate in vector_result.matches:
                provider_token = str(candidate.provider_id)
                provider_uuid = self._resolve_provider_uuid(provider_token)
                if provider_uuid is None:
                    continue
                if str(provider_uuid) in messaged_license_ids:
                    continue
                if provider_token in messaged_tokens:
                    continue
                if candidate.rank <= demand.retry_attempt_count:
                    continue
                selected = candidate
                break

            if selected is None:
                results.append(
                    RetryCascadeResult(
                        offer_id=demand.offer_id,
                        status="no_eligible_fallback",
                        retry_attempt_count=demand.retry_attempt_count,
                        selected_rank=None,
                        provider_id=None,
                        provider_name=None,
                        message="No higher-ranked fallback candidate available",
                    )
                )
                continue

            provider_uuid = self._resolve_provider_uuid(str(selected.provider_id))
            if provider_uuid is None:
                results.append(
                    RetryCascadeResult(
                        offer_id=demand.offer_id,
                        status="provider_unresolved",
                        retry_attempt_count=demand.retry_attempt_count,
                        selected_rank=selected.rank,
                        provider_id=str(selected.provider_id),
                        provider_name=selected.full_name,
                        message="Fallback candidate could not be resolved to provider UUID",
                    )
                )
                continue

            next_attempt = demand.retry_attempt_count + 1
            try:
                from app.models import OfferCareJobOffer

                offer = (
                    self.db.query(OfferCareJobOffer)
                    .filter(OfferCareJobOffer.offer_id == UUID(demand.offer_id))
                    .first()
                )
                self._trigger_dispatch_hook(
                    offer_id=UUID(demand.offer_id),
                    provider_uuid=provider_uuid,
                    provider_label=str(selected.full_name),
                    selected_rank=int(selected.rank),
                    retry_attempt_count=next_attempt,
                    broadcast_wave_id=offer.broadcast_wave_id if offer else None,
                )
                retry_meta["retry_attempt_count"] = next_attempt
                retry_meta["last_provider_id"] = str(selected.provider_id)
                retry_meta["last_rank"] = int(selected.rank)
                retry_meta["updated_at"] = _utc_now().isoformat()
                messaged = list(retry_meta.get("messaged_provider_ids") or [])
                if str(selected.provider_id) not in messaged:
                    messaged.append(str(selected.provider_id))
                retry_meta["messaged_provider_ids"] = messaged
                self._persist_retry_meta(UUID(demand.offer_id), retry_meta)
            except SQLAlchemyError as exc:
                self.db.rollback()
                raise MatchRetrySchedulerHardStop("retry_cascade_persist_failed") from exc

            results.append(
                RetryCascadeResult(
                    offer_id=demand.offer_id,
                    status="dispatched",
                    retry_attempt_count=next_attempt,
                    selected_rank=int(selected.rank),
                    provider_id=str(selected.provider_id),
                    provider_name=str(selected.full_name),
                    message=(
                        f"Fallback rank #{selected.rank} dispatched via semantic retry "
                        f"(engine={vector_result.engine})"
                    ),
                )
            )

        return results


if __name__ == "__main__":
    print("COMPILE_OK match_retry_scheduler")
    scheduler = MatchRetryScheduler(db=None)
    print(f"scheduler={scheduler.__class__.__name__} timeout={scheduler.retry_timeout_seconds}s")
