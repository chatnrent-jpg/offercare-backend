"""Maryland ops desk orchestrator — live PostgreSQL state with fixture fallback."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from strategy.backup_routing_engine import BackupRoutingEngine
from strategy.db_workforce_adapter import load_db_candidates
from strategy.placement_penalty_engine import PlacementPenaltyEngine
from strategy.schedule_conflict_engine import ScheduleConflictEngine
from strategy.surge_pricing_engine import SurgePricingEngine

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PIPELINE_LOG = _REPO_ROOT / "logs" / "manus" / "desk_pipeline_runs.json"
_DEFAULT_MANUS_HANDOFF = _REPO_ROOT / "logs" / "manus" / "manus_desk_handoff.json"
_DEFAULT_FIXTURE_ROOT = _REPO_ROOT / "logs" / "manus"
_DEFAULT_SHIFT_HOURS = 8.0
_MONTGOMERY_COUNTY_TOKEN = "montgomery"


class MarylandDeskOrchestratorHardStop(RuntimeError):
    """Hive halt — Maryland desk orchestrator import or DB failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_timestamp(value: str) -> datetime:
    token = str(value or "").strip()
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    parsed = datetime.fromisoformat(token)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_county(value: str | None) -> str:
    return re.sub(r"\s+county\s*$", "", str(value or "").strip(), flags=re.IGNORECASE)


def _is_montgomery_county(value: str | None) -> bool:
    return _MONTGOMERY_COUNTY_TOKEN in _normalize_county(value).lower()


def _shift_start_key(shift: dict[str, Any]) -> str:
    for key in ("shift_timestamp", "shift_starts_at", "start_time", "shift_start"):
        raw = shift.get(key)
        if raw:
            return str(raw)
    raise ValueError("shift must include shift_timestamp or start_time")


def _shift_interval(shift: dict[str, Any], duration_hours: float = _DEFAULT_SHIFT_HOURS) -> tuple[str, str]:
    start = _parse_timestamp(_shift_start_key(shift))
    end = start + timedelta(hours=duration_hours)
    return start.isoformat(), end.isoformat()


def _load_json_fixture(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("HIVE_MD_DESK: fixture read failed path=%s error=%s", path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


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


def provider_hours_from_timesheets(timesheets_payload: dict[str, Any], provider_id: str) -> float:
    total = 0.0
    for row in timesheets_payload.get("timesheets") or []:
        if str(row.get("provider_license_number") or "") != str(provider_id):
            continue
        total += float(row.get("hours_worked") or 0.0)
    return total


def _registry_from_db_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    applicants: list[dict[str, Any]] = []
    for row in candidates:
        verified = str(row.get("license_verified_at") or _utc_now_iso())
        applicants.append(
            {
                "name": row.get("full_name"),
                "license_type": row.get("role"),
                "license_number": row.get("provider_id"),
                "has_gna_endorsement": bool(row.get("has_gna_endorsement")),
                "county": row.get("county"),
                "verification_timestamp": verified,
                "placement_eligible": bool(row.get("placement_eligible", True)),
            }
        )
    return {"applicants": applicants}


class MarylandDeskOrchestrator:
    """Maryland SNF/CNA desk — live Postgres ingestion with explicit fixture fallback."""

    def __init__(
        self,
        workforce_registry: dict[str, Any] | None = None,
        active_commitments: list[dict[str, Any]] | None = None,
        *,
        timesheets_payload: dict[str, Any] | None = None,
        db: Session | None = None,
        facility_id: UUID | None = None,
        testing_mode: bool = False,
        use_fixtures: bool = False,
        fixture_root: Path | None = None,
        montgomery_only: bool = True,
    ) -> None:
        self._db = db
        self._owns_session = False
        self.testing_mode = bool(testing_mode)
        self.use_fixtures = bool(use_fixtures)
        self.fixture_root = fixture_root or _DEFAULT_FIXTURE_ROOT
        self.facility_id = facility_id
        self.montgomery_only = bool(montgomery_only)
        self._match_matrix_broker: Any | None = None

        self._use_fixture_layer = self.testing_mode or self.use_fixtures
        self.data_source = "fixtures" if self._use_fixture_layer else "postgresql"

        if self._use_fixture_layer:
            root = self.fixture_root
            self.workforce_registry = dict(
                workforce_registry
                or _load_json_fixture(root / "processed_providers.json")
                or {}
            )
            self.timesheets_payload = dict(
                timesheets_payload
                or _load_json_fixture(root / "reconciled_timesheets.json")
                or {}
            )
            self.open_shifts = list(_load_json_fixture(root / "active_shifts.json").get("shifts") or [])
            if active_commitments is not None:
                self.commitments = list(active_commitments)
            elif self.timesheets_payload:
                self.commitments = commitments_from_timesheets(self.timesheets_payload)
            else:
                self.commitments = []
        else:
            self.workforce_registry = {}
            self.timesheets_payload = {}
            self.open_shifts = []
            self.commitments = list(active_commitments or [])
            self._hydrate_live_state()

        self.conflict_engine = ScheduleConflictEngine(self.commitments)
        self.surge_engine = SurgePricingEngine()
        self.backup_engine = BackupRoutingEngine(self.workforce_registry)
        self.penalty_engine = PlacementPenaltyEngine()

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise MarylandDeskOrchestratorHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._match_matrix_broker is not None:
            try:
                self._match_matrix_broker.close()
            except Exception:  # noqa: BLE001
                pass
            self._match_matrix_broker = None
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _get_match_matrix_broker(self) -> Any:
        if self._match_matrix_broker is None:
            try:
                from strategy.unified_match_matrix_broker import UnifiedMatchMatrixBroker
            except Exception as exc:  # noqa: BLE001
                raise MarylandDeskOrchestratorHardStop("unified_match_matrix_broker_import_failed") from exc
            self._match_matrix_broker = UnifiedMatchMatrixBroker(db=self.db)
        return self._match_matrix_broker

    def _hydrate_live_state(self) -> None:
        candidates = self.load_providers_from_db()
        self.workforce_registry = _registry_from_db_candidates(candidates)
        self.open_shifts = self.load_shift_openings_from_db()
        if not self.commitments:
            self.commitments = self.load_commitments_from_db()
        self.backup_engine = BackupRoutingEngine(self.workforce_registry)
        self.conflict_engine = ScheduleConflictEngine(self.commitments)

    def load_providers_from_db(self, *, limit: int = 500) -> list[dict[str, Any]]:
        """Extract candidate records from maryland_providers."""
        try:
            candidates = load_db_candidates(self.db, facility_id=self.facility_id, limit=limit)
        except SQLAlchemyError as exc:
            raise MarylandDeskOrchestratorHardStop("provider_query_failed") from exc
        if self.montgomery_only:
            candidates = [
                row for row in candidates if _is_montgomery_county(str(row.get("county") or ""))
            ]
        return candidates

    def load_shift_openings_from_db(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Pull active facility shift openings from offercare_job_offers + ingested_open_shifts."""
        try:
            from app.models import IngestedOpenShift, MarylandFacility, OfferCareJobOffer
        except ImportError as exc:
            raise MarylandDeskOrchestratorHardStop("shift_models_import_failed") from exc

        try:
            rows = (
                self.db.query(OfferCareJobOffer, IngestedOpenShift, MarylandFacility)
                .outerjoin(IngestedOpenShift, IngestedOpenShift.offer_id == OfferCareJobOffer.offer_id)
                .join(MarylandFacility, MarylandFacility.facility_id == OfferCareJobOffer.facility_id)
                .filter(OfferCareJobOffer.assigned_provider_id.is_(None))
                .order_by(OfferCareJobOffer.created_at.desc())
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as exc:
            raise MarylandDeskOrchestratorHardStop("shift_opening_query_failed") from exc

        openings: list[dict[str, Any]] = []
        for offer, ingest, facility in rows:
            county = _normalize_county(facility.county)
            if self.montgomery_only and not _is_montgomery_county(county):
                continue
            role = str(offer.shift_role or (ingest.shift_role if ingest else "") or "CNA")
            shift_start = offer.shift_starts_at
            if shift_start is None and ingest is not None:
                try:
                    shift_start = _parse_timestamp(f"{ingest.shift_date}T{ingest.start_time}")
                except ValueError:
                    shift_start = None
            shift_start_iso = shift_start.isoformat() if shift_start is not None else _utc_now_iso()
            openings.append(
                {
                    "order_id": str(offer.offer_id),
                    "offer_id": str(offer.offer_id),
                    "facility_id": str(facility.facility_id),
                    "facility_name": facility.name,
                    "facility_type": facility.facility_type,
                    "county": county,
                    "required_role": role.split("_")[-1] if "_" in role else role,
                    "shift_role": role,
                    "shift_timestamp": shift_start_iso,
                    "shift_starts_at": shift_start_iso,
                    "start_time": ingest.start_time if ingest is not None else None,
                    "unit_dept": ingest.unit_dept if ingest is not None else None,
                    "hourly_pay_rate": float(offer.hourly_pay_rate or 0),
                    "compliance_lock_status": str(offer.compliance_lock_status or ""),
                    "ingest_source": ingest.source if ingest is not None else None,
                    "payload_json": ingest.payload_json if ingest is not None else None,
                }
            )
        return openings

    def load_commitments_from_db(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Build active clinician commitment pool from assigned live offers."""
        try:
            from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
        except ImportError as exc:
            raise MarylandDeskOrchestratorHardStop("commitment_models_import_failed") from exc

        try:
            rows = (
                self.db.query(OfferCareJobOffer, MarylandProvider, MarylandFacility)
                .join(MarylandProvider, MarylandProvider.provider_id == OfferCareJobOffer.assigned_provider_id)
                .join(MarylandFacility, MarylandFacility.facility_id == OfferCareJobOffer.facility_id)
                .filter(OfferCareJobOffer.assigned_provider_id.isnot(None))
                .filter(OfferCareJobOffer.shift_starts_at.isnot(None))
                .order_by(OfferCareJobOffer.shift_starts_at.desc())
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as exc:
            logger.warning("HIVE_MD_DESK: commitment query failed error=%s", exc)
            return []

        commitments: list[dict[str, Any]] = []
        for offer, provider, facility in rows:
            county = _normalize_county(facility.county)
            if self.montgomery_only and not _is_montgomery_county(county):
                continue
            shift = {
                "shift_timestamp": offer.shift_starts_at.isoformat() if offer.shift_starts_at else _utc_now_iso(),
                "county": county,
            }
            start_iso, end_iso = _shift_interval(shift)
            commitments.append(
                {
                    "provider_id": provider.md_license_number,
                    "provider_name": provider.full_name,
                    "order_id": str(offer.offer_id),
                    "facility_name": facility.name,
                    "county": county,
                    "shift_start": start_iso,
                    "shift_end": end_iso,
                }
            )
        return commitments

    def refresh_live_state(self) -> dict[str, Any]:
        """Re-query Postgres workforce, openings, and commitments."""
        if self._use_fixture_layer:
            return {
                "ok": True,
                "data_source": "fixtures",
                "provider_count": len(self.workforce_registry.get("applicants") or []),
                "opening_count": len(self.open_shifts),
                "commitment_count": len(self.commitments),
            }
        self._hydrate_live_state()
        return {
            "ok": True,
            "data_source": "postgresql",
            "provider_count": len(self.workforce_registry.get("applicants") or []),
            "opening_count": len(self.open_shifts),
            "commitment_count": len(self.commitments),
        }

    def _normalize_shift_request(self, shift: dict[str, Any]) -> dict[str, Any]:
        return {
            "order_id": shift.get("order_id") or shift.get("offer_id"),
            "offer_id": shift.get("offer_id") or shift.get("order_id"),
            "facility_id": shift.get("facility_id"),
            "facility_name": shift.get("facility_name"),
            "facility_type": shift.get("facility_type"),
            "required_role": shift.get("required_role"),
            "county": shift.get("county"),
            "facility_county": shift.get("county"),
            "shift_timestamp": _shift_start_key(shift),
            "evaluation_window_barrier": _shift_start_key(shift),
            "unit_dept": shift.get("unit_dept"),
        }

    def _shift_context_for_broker(self, shift: dict[str, Any], evaluation_timestamp: str) -> dict[str, Any]:
        normalized = self._normalize_shift_request(shift)
        qualifiers = " ".join(
            str(shift.get(key) or "")
            for key in ("unit_dept", "payload_json", "qualifiers", "shift_role")
        ).strip()
        return {
            **normalized,
            "shift_starts_at": normalized.get("shift_timestamp"),
            "evaluation_timestamp": evaluation_timestamp,
            "qualifiers": qualifiers,
            "query_text": shift.get("query_text") or qualifiers,
            "urgent": shift.get("urgent"),
            "use_live_db": not self._use_fixture_layer,
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
        shift_id = str(shift_request.get("offer_id") or shift_request.get("order_id") or "desk-shift")
        shift_context = self._shift_context_for_broker(shift, evaluation_timestamp)

        broker = self._get_match_matrix_broker()
        matrix_result = broker.resolve_canonical_shift_matches(shift_id, shift_context)
        matches = list(matrix_result.get("matches") or [])

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
                "rank": match.get("rank"),
                "similarity_score": match.get("similarity_score"),
                "compliance_status": match.get("compliance_status"),
                "is_eligible": match.get("is_eligible"),
                "routing_engine": matrix_result.get("routing_engine"),
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
            "matcher_source": self.data_source,
            "routing_engine": matrix_result.get("routing_engine"),
            "matrix_urgent": matrix_result.get("urgent"),
            "matrix_tag_dense": matrix_result.get("tag_dense"),
            "raw_match_count": matrix_result.get("raw_match_count"),
            "selected_provider": selected,
            "booking_candidates": booking_candidates[:5],
            "surge_pricing": surge,
            "active_commitments_count": len(self.commitments),
        }

    def run_callout_pipeline(self, disrupted_shift_id: str, original_provider_id: str) -> dict[str, Any]:
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
                    facility_id=facility_id
                    or f"MD-SNF-{str(shift.get('facility_name', 'UNKNOWN'))[:12].upper().replace(' ', '-')}",
                    provider_id=provider_id,
                )

        return {
            "run_id": f"desk-{_utc_now_iso()}",
            "staged_at_utc": _utc_now_iso(),
            "live_execution": not self._use_fixture_layer,
            "mode": "FIXTURES" if self._use_fixture_layer else "LIVE",
            "data_source": self.data_source,
            "product": "VettedMe.ai Maryland Desk Orchestrator",
            "booking": booking,
            "callout": callout,
            "penalty": penalty,
            "open_shift_count": len(self.open_shifts),
            "provider_pool_count": len(self.workforce_registry.get("applicants") or []),
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
                "mode": payload.get("mode", "LIVE"),
                "live_execution": bool(payload.get("live_execution")),
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
        "schema_version": "1.1",
        "product": "VettedMe.ai Maryland Ops Desk — Manus Handoff",
        "architecture": "Manus acts (scrape, stage JSON, trigger scripts) · VettedMe decides (engine chain)",
        "live_execution": True,
        "default_data_source": "postgresql",
        "fixture_flags": ["testing_mode", "use_fixtures"],
        "operator_workflows": [
            {
                "id": "live-desk-cycle",
                "title": "Execute Maryland desk orchestrator (live Postgres)",
                "command": "python strategy/maryland_desk_orchestrator.py",
                "output": "logs/manus/desk_pipeline_runs.json",
            },
            {
                "id": "fixture-desk-cycle",
                "title": "Execute desk orchestrator with JSON fixtures",
                "command": "python strategy/maryland_desk_orchestrator.py --fixtures",
                "output": "logs/manus/desk_pipeline_runs.json",
            },
        ],
        "engine_chain": [
            "strategy/unified_match_matrix_broker.py",
            "strategy/credential_check_engine.py",
            "strategy/compliance_authority_anchor.py",
            "strategy/schedule_conflict_engine.py",
            "strategy/surge_pricing_engine.py",
            "strategy/backup_routing_engine.py",
            "strategy/placement_penalty_engine.py",
            "strategy/maryland_desk_orchestrator.py",
        ],
        "filesystem_paths": {
            "repo_root": str(root),
            "processed_providers": str(root / "logs/manus/processed_providers.json"),
            "active_shifts": str(root / "logs/manus/active_shifts.json"),
            "reconciled_timesheets": str(root / "logs/manus/reconciled_timesheets.json"),
            "desk_pipeline_runs": str(root / "logs/manus/desk_pipeline_runs.json"),
            "ops_console": str(root / "ui_dashboard/ops_console.py"),
        },
        "api_recruitment_prefix": "/api/vettedme/manus/recruitment",
        "api_credential_prefix": "/api/vettedme/manus",
        "generated_at_utc": _utc_now_iso(),
    }


# Backward-compatible alias for legacy test runners.
DeskOrchestrator = MarylandDeskOrchestrator


if __name__ == "__main__":
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(description="Maryland desk orchestrator self-test")
    parser.add_argument("--fixtures", action="store_true", help="Run against JSON fixture layer")
    parser.add_argument("--live", action="store_true", help="Attempt live Postgres hydration")
    args = parser.parse_args()
    use_fixtures = args.fixtures or not args.live

    print("COMPILE_OK maryland_desk_orchestrator")

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

    orchestrator = MarylandDeskOrchestrator(
        mock_registry if use_fixtures else None,
        timesheets_payload=mock_timesheets if use_fixtures else None,
        testing_mode=use_fixtures,
        use_fixtures=use_fixtures,
    )
    result = orchestrator.run_full_desk_cycle(
        shift,
        evaluation_timestamp="2026-06-27T10:00:00+00:00",
    )
    assert result["booking"]["status"] in {"BOOKING_READY", "CONFLICT_BLOCKED", "NO_SAFE_ASSIGNMENT"}
    assert "surge_pricing" in result["booking"]
    assert result["mode"] == ("FIXTURES" if use_fixtures else "LIVE")

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "desk_pipeline_runs.json"
        MarylandDeskOrchestrator.persist_run(result, log_path)
        assert log_path.is_file()

    orchestrator.close()
    print(f"MarylandDeskOrchestrator self-test passed mode={result['mode']}")
