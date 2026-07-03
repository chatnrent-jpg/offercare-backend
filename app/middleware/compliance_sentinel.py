"""Maryland compliance sentinel — HB 1106 anti-bias consent + MBON freshness gate.

Strict logic gate evaluated before matching caregivers to nursing-home (SNF) shifts.
Records encrypted audit rows intended for automated Maryland state reporting.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    LicenseVerificationLog,
    MarylandProvider,
    MdProviderCompliance,
    MdProviderLicensure,
)
from app.services.worker_consent import (
    provider_has_hb1106_automated_hiring_consent,
    resolve_provider_consent_signed_at,
)

logger = logging.getLogger(__name__)

COMPLIANCE_SENTINEL_CLEAR = "COMPLIANCE_SENTINEL_CLEAR"
COMPLIANCE_SENTINEL_MATCHING_HOLD = "COMPLIANCE_SENTINEL_MATCHING_HOLD"
COMPLIANCE_SENTINEL_BLOCKED = "COMPLIANCE_SENTINEL_BLOCKED"

REASON_HB1106_CONSENT_MISSING = "hb1106_anti_bias_consent_missing"
REASON_MBON_VERIFICATION_MISSING = "mbon_verification_missing"
REASON_MBON_VERIFICATION_STALE = "mbon_verification_stale"

STATE_REPORTING_SCHEMA = "MD_AUTOMATED_HIRING_COMPLIANCE_v1"
STATUTE_REFERENCE = "Maryland HB 1106"

_NURSING_HOME_FACILITY_TYPES = frozenset(
    {
        "SNF",
        "NURSING_HOME",
        "SKILLED_NURSING",
        "LONG_TERM_CARE",
        "LTC",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_nursing_home_shift(*, facility_type: str | None = None, shift_context: dict[str, Any] | None = None) -> bool:
    """Return True when the shift targets a skilled-nursing / nursing-home setting."""
    token = str(facility_type or "").strip().upper()
    if not token and shift_context:
        token = str(shift_context.get("facility_type") or "").strip().upper()
    if not token:
        return False
    if token in _NURSING_HOME_FACILITY_TYPES:
        return True
    return "NURSING" in token and "HOME" in token


def resolve_mbon_verification_timestamp(
    db: Session,
    provider_id: UUID,
) -> datetime | None:
    """Latest MBON verification timestamp from compliance tables or provider profile."""
    compliance = (
        db.query(MdProviderCompliance)
        .filter(MdProviderCompliance.provider_id == provider_id)
        .first()
    )
    if compliance and compliance.mbon_status_last_checked is not None:
        return _ensure_aware(compliance.mbon_status_last_checked)

    licensure = (
        db.query(MdProviderLicensure)
        .filter(MdProviderLicensure.provider_id == provider_id)
        .first()
    )
    if licensure and licensure.mbon_status_last_checked is not None:
        return _ensure_aware(licensure.mbon_status_last_checked)

    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider and provider.last_verified_timestamp is not None:
        return _ensure_aware(provider.last_verified_timestamp)
    return None


@dataclass(frozen=True)
class ComplianceSentinelVerdict:
    allowed: bool
    matching_hold: bool
    blocked: bool
    compliance_status: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    hb1106_consent_signed_at: datetime | None = None
    mbon_verification_checked_at: datetime | None = None
    mbon_verification_age_hours: float | None = None
    mbon_max_age_hours: int = 24
    statute: str = STATUTE_REFERENCE
    reporting_schema: str = STATE_REPORTING_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("hb1106_consent_signed_at", "mbon_verification_checked_at"):
            value = payload.get(key)
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
        return payload


def _import_compliance_audit_ledger() -> Any:
    try:
        import importlib.util
        from pathlib import Path

        module_path = Path(__file__).resolve().parents[1] / "models" / "compliance_audit_ledger.py"
        spec = importlib.util.spec_from_file_location("compliance_audit_ledger", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("compliance_audit_ledger_import_failed")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.ComplianceAuditLedger
    except Exception as exc:  # noqa: BLE001
        raise ImportError("compliance_audit_ledger_import_failed") from exc


def _persist_state_reporting_audit(
    *,
    db: Session | None,
    provider_id: UUID | str,
    verdict: ComplianceSentinelVerdict,
    shift_id: str | None = None,
    shift_context: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> None:
    """Write encrypted compliance audit ledger row for automated state reporting."""
    if db is None:
        try:
            from app.database import SessionLocal

            session = SessionLocal()
            try:
                _persist_state_reporting_audit(
                    db=session,
                    provider_id=provider_id,
                    verdict=verdict,
                    shift_id=shift_id,
                    shift_context=shift_context,
                    candidate=candidate,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("compliance_sentinel audit persist skipped: %s", exc)
        return

    try:
        ComplianceAuditLedger = _import_compliance_audit_ledger()
        context = dict(shift_context or {})
        if candidate:
            context.setdefault("candidate_provider_id", candidate.get("provider_id"))
            context.setdefault("candidate_license", candidate.get("license_number"))

        raw_payload = {
            "reporting_schema": verdict.reporting_schema,
            "statute": verdict.statute,
            "gate": "COMPLIANCE_SENTINEL",
            "provider_id": str(provider_id),
            "shift_id": shift_id,
            "facility_type": context.get("facility_type"),
            "facility_id": context.get("facility_id"),
            "verdict": verdict.compliance_status,
            "allowed": verdict.allowed,
            "matching_hold": verdict.matching_hold,
            "blocked": verdict.blocked,
            "reasons": list(verdict.reasons),
            "hb1106_consent_signed_at": (
                verdict.hb1106_consent_signed_at.isoformat()
                if verdict.hb1106_consent_signed_at
                else None
            ),
            "mbon_verification_checked_at": (
                verdict.mbon_verification_checked_at.isoformat()
                if verdict.mbon_verification_checked_at
                else None
            ),
            "mbon_verification_age_hours": verdict.mbon_verification_age_hours,
            "mbon_max_age_hours": verdict.mbon_max_age_hours,
            "checked_at_utc": _utc_now().isoformat(),
            "shift_context": context,
        }

        payload_json = json.dumps(raw_payload, default=str)
        row = ComplianceAuditLedger(
            provider_id=str(provider_id),
            timesheet_token=str(shift_id or context.get("offer_id") or "").strip() or None,
            compliance_status=verdict.compliance_status,
            is_eligible=verdict.allowed,
        )
        try:
            row.raw_payload_json = payload_json
        except Exception:  # noqa: BLE001
            row._encrypted_payload_json = payload_json
        db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("compliance_sentinel ledger write skipped provider=%s error=%s", provider_id, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def evaluate_compliance_sentinel(
    db: Session,
    provider_id: UUID,
    *,
    facility_type: str | None = None,
    shift_context: dict[str, Any] | None = None,
    shift_id: str | None = None,
    candidate: dict[str, Any] | None = None,
    persist_audit: bool = True,
    reference_time: datetime | None = None,
) -> ComplianceSentinelVerdict:
    """Evaluate HB 1106 consent + MBON freshness for nursing-home shift matching."""
    if not settings.COMPLIANCE_SENTINEL_ENABLED:
        return ComplianceSentinelVerdict(
            allowed=True,
            matching_hold=False,
            blocked=False,
            compliance_status=COMPLIANCE_SENTINEL_CLEAR,
        )

    if not is_nursing_home_shift(facility_type=facility_type, shift_context=shift_context):
        return ComplianceSentinelVerdict(
            allowed=True,
            matching_hold=False,
            blocked=False,
            compliance_status=COMPLIANCE_SENTINEL_CLEAR,
        )

    now = _ensure_aware(reference_time or _utc_now())
    max_age_hours = int(settings.COMPLIANCE_SENTINEL_MBON_MAX_AGE_HOURS)
    reasons: list[str] = []
    matching_hold = False
    blocked = False

    hb1106_signed_at: datetime | None = None
    if settings.COMPLIANCE_SENTINEL_HB1106_REQUIRED:
        hb1106_signed_at = resolve_provider_consent_signed_at(db, provider_id)
        if hb1106_signed_at is None:
            reasons.append(REASON_HB1106_CONSENT_MISSING)
            matching_hold = True

    mbon_checked_at = resolve_mbon_verification_timestamp(db, provider_id)
    mbon_age_hours: float | None = None
    if mbon_checked_at is None:
        reasons.append(REASON_MBON_VERIFICATION_MISSING)
        blocked = True
    else:
        mbon_age_hours = (now - mbon_checked_at).total_seconds() / 3600.0
        if mbon_age_hours > float(max_age_hours):
            reasons.append(REASON_MBON_VERIFICATION_STALE)
            blocked = True

    allowed = not reasons
    if allowed:
        status = COMPLIANCE_SENTINEL_CLEAR
    elif blocked:
        status = COMPLIANCE_SENTINEL_BLOCKED
    else:
        status = COMPLIANCE_SENTINEL_MATCHING_HOLD

    verdict = ComplianceSentinelVerdict(
        allowed=allowed,
        matching_hold=matching_hold and not blocked,
        blocked=blocked,
        compliance_status=status,
        reasons=tuple(reasons),
        hb1106_consent_signed_at=hb1106_signed_at,
        mbon_verification_checked_at=mbon_checked_at,
        mbon_verification_age_hours=mbon_age_hours,
        mbon_max_age_hours=max_age_hours,
    )

    if persist_audit and not allowed:
        _persist_state_reporting_audit(
            db=db,
            provider_id=provider_id,
            verdict=verdict,
            shift_id=shift_id,
            shift_context=shift_context,
            candidate=candidate,
        )

    return verdict


def evaluate_compliance_sentinel_for_provider(
    db: Session,
    provider: MarylandProvider,
    *,
    shift_context: dict[str, Any] | None = None,
    shift_id: str | None = None,
    persist_audit: bool = True,
) -> ComplianceSentinelVerdict:
    """Provider ORM wrapper for sentinel evaluation."""
    facility_type = str((shift_context or {}).get("facility_type") or "")
    return evaluate_compliance_sentinel(
        db,
        provider.provider_id,
        facility_type=facility_type,
        shift_context=shift_context,
        shift_id=shift_id,
        persist_audit=persist_audit,
    )


def evaluate_compliance_sentinel_for_candidate_dict(
    db: Session,
    candidate: dict[str, Any],
    *,
    shift_context: dict[str, Any] | None = None,
    shift_id: str | None = None,
    persist_audit: bool = True,
) -> ComplianceSentinelVerdict:
    """Strategy-layer candidate dict wrapper — resolves provider UUID when present."""
    provider_uuid_raw = str(candidate.get("provider_uuid") or "").strip()
    if provider_uuid_raw:
        try:
            provider_id = UUID(provider_uuid_raw)
        except ValueError:
            provider_id = None
    else:
        provider_id = None

    if provider_id is None:
        license_token = str(candidate.get("license_number") or candidate.get("provider_id") or "").strip()
        if license_token:
            row = (
                db.query(MarylandProvider)
                .filter(MarylandProvider.md_license_number == license_token.upper())
                .first()
            )
            if row is not None:
                provider_id = row.provider_id

    if provider_id is None:
        verdict = ComplianceSentinelVerdict(
            allowed=False,
            matching_hold=False,
            blocked=True,
            compliance_status=COMPLIANCE_SENTINEL_BLOCKED,
            reasons=(REASON_MBON_VERIFICATION_MISSING,),
        )
        if persist_audit:
            _persist_state_reporting_audit(
                db=db,
                provider_id=str(candidate.get("provider_id") or "unknown"),
                verdict=verdict,
                shift_id=shift_id,
                shift_context=shift_context,
                candidate=candidate,
            )
        return verdict

    return evaluate_compliance_sentinel(
        db,
        provider_id,
        facility_type=str((shift_context or {}).get("facility_type") or ""),
        shift_context=shift_context,
        shift_id=shift_id,
        candidate=candidate,
        persist_audit=persist_audit,
    )


def record_hb1106_consent_event(
    db: Session,
    provider_id: UUID,
    *,
    consent_version: str | None = None,
    client_ip: str | None = None,
    commit: bool = False,
) -> LicenseVerificationLog:
    """Persist HB 1106 automated hiring anti-bias consent for sentinel clearance."""
    from app.services.worker_consent import (
        WORKER_CONSENT_VERSION,
        record_maryland_aedt_consent,
    )

    signed_at = record_maryland_aedt_consent(
        db,
        provider_id,
        consent_version=str(consent_version or WORKER_CONSENT_VERSION),
        client_ip=client_ip,
        commit=False,
    )
    db.flush()
    row = provider_has_hb1106_automated_hiring_consent(db, provider_id)
    if row is None:
        raise RuntimeError("aedt_consent_log_missing")
    if commit:
        db.commit()
        db.refresh(row)
    _ = signed_at
    return row
