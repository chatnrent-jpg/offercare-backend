"""Montgomery live backup dispatch → sequential SMS notify cascade (dry-run safe)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandProvider, OfferCareJobOffer, ShiftNotificationLog
from app.services.md_desk_production_loader import SLICE_COUNTY, SLICE_FACILITY_TYPE, SLICE_ROLE
from app.services.sms import SmsResult, send_shift_sms
from app.services.worker_consent import provider_has_sms_dispatch_consent

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NOTIFY_LOG = _REPO_ROOT / "logs" / "manus" / "backup_notify_cascade.json"
_ACTIVE_CASCADE_PATH = _REPO_ROOT / "logs" / "manus" / "backup_cascade_active.json"
_SLICE_KEY = f"{SLICE_COUNTY}_{SLICE_FACILITY_TYPE}_{SLICE_ROLE}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_callout_message(
    *,
    facility_name: str,
    required_role: str,
    rank: int,
    county: str,
) -> str:
    return (
        f"VettedCare.ai EMERGENCY CALLOUT · {facility_name} · {county} · "
        f"{required_role} backup #{rank}. Urgent same-day coverage needed. "
        f"Reply YES to accept. Reply STOP to opt out."
    )


def _resolve_offer_id(db: Session, disrupted_shift_id: str) -> UUID | None:
    token = str(disrupted_shift_id or "").strip()
    if not token:
        return None
    try:
        return UUID(token)
    except ValueError:
        return None


def _load_active_store() -> dict[str, Any]:
    if not _ACTIVE_CASCADE_PATH.is_file():
        return {"cascades": {}}
    payload = json.loads(_ACTIVE_CASCADE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload.get("cascades"), dict):
        payload["cascades"] = {}
    return payload


def _save_active_store(store: dict[str, Any]) -> None:
    _ACTIVE_CASCADE_PATH.parent.mkdir(parents=True, exist_ok=True)
    store["updated_at_utc"] = _utc_now_iso()
    _ACTIVE_CASCADE_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _persist_notify_log(payload: dict[str, Any]) -> Path:
    _NOTIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
    if _NOTIFY_LOG.is_file():
        existing = json.loads(_NOTIFY_LOG.read_text(encoding="utf-8"))
        events = existing.get("events") if isinstance(existing.get("events"), list) else []
    else:
        existing = {
            "mode": "PRODUCTION_SLICE",
            "product": "VettedCare.ai Backup Notify Cascade",
            "events": [],
        }
        events = []

    events.append(payload)
    existing["events"] = events
    existing["count"] = len(events)
    existing["updated_at_utc"] = _utc_now_iso()
    existing["live_execution"] = bool(payload.get("live_execution"))
    _NOTIFY_LOG.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return _NOTIFY_LOG


@dataclass(frozen=True)
class BackupCascadeAdvanceResult:
    status: str
    message: str
    dispatch_id: str
    notification: dict[str, Any] | None
    cascade: dict[str, Any]


def _offer_blocks_cascade(db: Session, offer_id: UUID | None, *, sent_count: int) -> tuple[bool, str | None]:
    if offer_id is None:
        return False, None
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is None:
        return False, None
    status = str(offer.compliance_lock_status or "").upper()
    if status == "BROADCASTING":
        return False, status
    if status == "LOCKED" and sent_count == 0:
        return False, status
    if status == "LOCKED":
        return True, status
    return True, status or "UNKNOWN"


def _set_offer_broadcasting(db: Session, offer_id: UUID | None) -> None:
    if offer_id is None:
        return
    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if offer is not None and str(offer.compliance_lock_status or "").upper() == "LOCKED":
        offer.compliance_lock_status = "BROADCASTING"


def _notified_license_numbers(session: dict[str, Any]) -> set[str]:
    return {
        str(row.get("provider_id") or "")
        for row in session.get("notified") or []
        if str(row.get("provider_id") or "")
    }


def _resolve_provider(db: Session, license_number: str) -> MarylandProvider | None:
    return (
        db.query(MarylandProvider)
        .filter(MarylandProvider.md_license_number == license_number)
        .first()
    )


def _evaluate_provider(
    db: Session,
    backup: dict[str, Any],
    *,
    offer_id: UUID | None,
    facility_name: str,
    required_role: str,
    county: str,
    commit_log: bool,
) -> dict[str, Any]:
    license_number = str(backup.get("provider_id") or "")
    rank = int(backup.get("rank") or 0)
    provider = _resolve_provider(db, license_number)
    if provider is None:
        return {
            "provider_id": license_number,
            "rank": rank,
            "status": "SKIPPED",
            "mode": "provider_not_found",
        }

    message_body = _build_callout_message(
        facility_name=facility_name,
        required_role=required_role,
        rank=rank,
        county=county,
    )

    if not provider_has_sms_dispatch_consent(
        db,
        provider.provider_id,
        email=provider.email,
        provider=provider,
    ):
        if offer_id is not None:
            db.add(
                ShiftNotificationLog(
                    offer_id=offer_id,
                    provider_id=provider.provider_id,
                    channel="SMS",
                    status="SKIPPED",
                    message_body=message_body,
                    broadcast_wave_id=None,
                )
            )
        return {
            "provider_id": license_number,
            "provider_uuid": str(provider.provider_id),
            "name": backup.get("name") or provider.full_name,
            "rank": rank,
            "phone_number": provider.phone_number,
            "status": "SKIPPED",
            "mode": "no_sms_consent",
            "message_preview": message_body[:120] + "…",
            "notified_at_utc": _utc_now_iso(),
        }

    sms: SmsResult = send_shift_sms(to_number=provider.phone_number, message_body=message_body)
    if offer_id is not None:
        db.add(
            ShiftNotificationLog(
                offer_id=offer_id,
                provider_id=provider.provider_id,
                channel="SMS",
                status=sms.status,
                message_body=message_body,
                broadcast_wave_id=None,
            )
        )
    if commit_log:
        db.commit()

    return {
        "provider_id": license_number,
        "provider_uuid": str(provider.provider_id),
        "name": backup.get("name") or provider.full_name,
        "rank": rank,
        "phone_number": provider.phone_number,
        "status": sms.status,
        "mode": sms.mode,
        "message_preview": message_body[:120] + "…",
        "notified_at_utc": _utc_now_iso(),
    }


def _next_backup_candidate(session: dict[str, Any]) -> dict[str, Any] | None:
    seen = _notified_license_numbers(session)
    for backup in session.get("backups") or []:
        license_number = str(backup.get("provider_id") or "")
        if license_number and license_number not in seen:
            return backup
    return None


def get_backup_cascade_status(db: Session, dispatch_id: str) -> dict[str, Any]:
    store = _load_active_store()
    session = store.get("cascades", {}).get(dispatch_id)
    if session is None:
        raise ValueError("backup_cascade_not_found")

    offer_id = _resolve_offer_id(db, str(session.get("disrupted_shift_id") or ""))
    notified = list(session.get("notified") or [])
    last_row = notified[-1] if notified else None
    last_sent_row = next(
        (row for row in reversed(notified) if str(row.get("status")) in {"DRY_RUN", "SENT"}),
        None,
    )
    last_notified_at = _parse_utc(last_sent_row.get("notified_at_utc") if last_sent_row else None)
    timeout = int(settings.SNIPER_CASCADE_TIMEOUT_SECONDS)
    next_eligible_at = None
    seconds_until_eligible = 0
    if last_notified_at is not None:
        next_eligible_at = (last_notified_at + timedelta(seconds=timeout)).isoformat()
        seconds_until_eligible = max(0, int((last_notified_at + timedelta(seconds=timeout) - _utc_now()).total_seconds()))

    sent_count = sum(
        1
        for row in notified
        if str(row.get("status")) in {"DRY_RUN", "SENT"}
    )
    blocked, offer_status = _offer_blocks_cascade(db, offer_id, sent_count=sent_count)
    next_candidate = _next_backup_candidate(session)
    cascade_enabled = settings.SNIPER_CASCADE_ENABLED
    max_recipients = int(settings.SNIPER_CASCADE_MAX_RECIPIENTS)
    session_status = str(session.get("status") or "ACTIVE")

    if blocked and offer_status == "LOCKED":
        session_status = "LOCKED"
    elif next_candidate is None:
        session_status = "EXHAUSTED"

    can_advance = (
        cascade_enabled
        and session_status == "ACTIVE"
        and not blocked
        and next_candidate is not None
        and sent_count < max_recipients
        and seconds_until_eligible == 0
    )

    return {
        "dispatch_id": dispatch_id,
        "slice_key": session.get("slice_key"),
        "offer_id": str(offer_id) if offer_id else session.get("offer_id"),
        "status": session_status,
        "cascade_enabled": cascade_enabled,
        "timeout_seconds": timeout,
        "notified_count": len(notified),
        "sent_count": sent_count,
        "max_recipients": max_recipients,
        "last_notified_at_utc": last_row.get("notified_at_utc") if last_row else None,
        "next_eligible_at_utc": next_eligible_at,
        "seconds_until_eligible": seconds_until_eligible,
        "notified": notified,
        "next_candidate": next_candidate,
        "can_advance": can_advance,
        "offer_status": offer_status,
    }


def advance_backup_notify_cascade(
    db: Session,
    dispatch_id: str,
    *,
    force: bool = False,
    actor: str = "backup_cascade",
    persist: bool = True,
) -> BackupCascadeAdvanceResult:
    if not settings.SNIPER_CASCADE_ENABLED:
        cascade = get_backup_cascade_status(db, dispatch_id)
        return BackupCascadeAdvanceResult(
            status="disabled",
            message="Backup notify cascade is disabled.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )

    store = _load_active_store()
    session = store.get("cascades", {}).get(dispatch_id)
    if session is None:
        raise ValueError("backup_cascade_not_found")

    cascade = get_backup_cascade_status(db, dispatch_id)
    if cascade["status"] == "LOCKED":
        return BackupCascadeAdvanceResult(
            status="already_locked",
            message="Shift already locked via YES reply.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )
    if cascade["status"] == "EXHAUSTED":
        return BackupCascadeAdvanceResult(
            status="exhausted",
            message="No more backup clinicians to notify.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )
    if cascade["next_candidate"] is None:
        session["status"] = "EXHAUSTED"
        store["cascades"][dispatch_id] = session
        _save_active_store(store)
        cascade = get_backup_cascade_status(db, dispatch_id)
        return BackupCascadeAdvanceResult(
            status="exhausted",
            message="No more backup clinicians to notify.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )
    if cascade["sent_count"] >= cascade["max_recipients"]:
        session["status"] = "EXHAUSTED"
        store["cascades"][dispatch_id] = session
        _save_active_store(store)
        cascade = get_backup_cascade_status(db, dispatch_id)
        return BackupCascadeAdvanceResult(
            status="exhausted",
            message="Cascade recipient limit reached.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )
    if not force and cascade["seconds_until_eligible"] > 0:
        return BackupCascadeAdvanceResult(
            status="too_early",
            message=f"Wait {cascade['seconds_until_eligible']}s before notifying the next clinician.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )

    shift = session.get("shift") or {}
    facility_name = str(shift.get("facility_name") or "Arbor Ridge at Riderwood")
    required_role = str(shift.get("required_role") or SLICE_ROLE)
    county = str(shift.get("county") or SLICE_COUNTY)
    offer_id = _resolve_offer_id(db, str(session.get("disrupted_shift_id") or ""))

    notification: dict[str, Any] | None = None
    backups = list(session.get("backups") or [])
    seen = _notified_license_numbers(session)
    for backup in backups:
        license_number = str(backup.get("provider_id") or "")
        if not license_number or license_number in seen:
            continue
        row = _evaluate_provider(
            db,
            backup,
            offer_id=offer_id,
            facility_name=facility_name,
            required_role=required_role,
            county=county,
            commit_log=False,
        )
        session.setdefault("notified", []).append(row)
        seen.add(license_number)
        if str(row.get("status")) == "SKIPPED":
            continue
        notification = row
        break

    if notification is None:
        session["status"] = "EXHAUSTED"
        store["cascades"][dispatch_id] = session
        _save_active_store(store)
        db.commit()
        cascade = get_backup_cascade_status(db, dispatch_id)
        return BackupCascadeAdvanceResult(
            status="exhausted",
            message="No consent-eligible backup clinicians remain.",
            dispatch_id=dispatch_id,
            notification=None,
            cascade=cascade,
        )

    _set_offer_broadcasting(db, offer_id)
    db.commit()
    session["last_advanced_by"] = actor
    session["updated_at_utc"] = _utc_now_iso()
    store["cascades"][dispatch_id] = session
    _save_active_store(store)

    event = {
        "event_type": "ADVANCE",
        "dispatch_id": dispatch_id,
        "live_execution": True,
        "slice_key": session.get("slice_key"),
        "notification": notification,
        "cascade_status": get_backup_cascade_status(db, dispatch_id),
        "staged_at_utc": _utc_now_iso(),
        "sms_dry_run": settings.SMS_DRY_RUN,
    }
    if persist:
        event["log_path"] = str(_persist_notify_log(event).relative_to(_REPO_ROOT)).replace("\\", "/")

    updated = get_backup_cascade_status(db, dispatch_id)
    return BackupCascadeAdvanceResult(
        status="advanced",
        message=f"Notified {notification.get('name')} (rank #{notification.get('rank')}).",
        dispatch_id=dispatch_id,
        notification=notification,
        cascade=updated,
    )


def notify_montgomery_backup_cascade(
    db: Session,
    dispatch: dict[str, Any],
    *,
    persist: bool = True,
) -> dict[str, Any]:
    if not dispatch.get("live_execution"):
        raise ValueError("backup notify cascade requires live_execution dispatch")

    slice_key = str(dispatch.get("slice_key") or _SLICE_KEY)
    if slice_key != _SLICE_KEY:
        raise ValueError(f"backup notify cascade limited to slice {_SLICE_KEY}")

    dispatch_id = str(dispatch.get("dispatch_id") or "")
    if not dispatch_id:
        raise ValueError("dispatch_id required for backup notify cascade")

    backups = list(dispatch.get("backup_candidates") or [])
    shift = dispatch.get("shift") or {}
    offer_id = _resolve_offer_id(db, str(dispatch.get("disrupted_shift_id") or ""))

    if not backups:
        result = {
            "ok": True,
            "status": "NO_BACKUPS_TO_NOTIFY",
            "live_execution": True,
            "slice_key": slice_key,
            "dispatch_id": dispatch_id,
            "notifications": [],
            "cascade": None,
            "sms_dry_run": settings.SMS_DRY_RUN,
        }
        if persist:
            result["log_path"] = str(_persist_notify_log({**result, "staged_at_utc": _utc_now_iso()}).relative_to(_REPO_ROOT))
        return result

    store = _load_active_store()
    session = {
        "dispatch_id": dispatch_id,
        "slice_key": slice_key,
        "disrupted_shift_id": dispatch.get("disrupted_shift_id"),
        "offer_id": str(offer_id) if offer_id else None,
        "shift": shift,
        "backups": backups[: int(settings.SNIPER_CASCADE_MAX_RECIPIENTS)],
        "notified": [],
        "status": "ACTIVE",
        "created_at_utc": _utc_now_iso(),
    }
    store.setdefault("cascades", {})[dispatch_id] = session
    _save_active_store(store)

    _set_offer_broadcasting(db, offer_id)

    advance = advance_backup_notify_cascade(db, dispatch_id, force=True, actor="live_callout", persist=False)
    cascade = advance.cascade or get_backup_cascade_status(db, dispatch_id)
    notifications = list(cascade.get("notified") or [])

    result = {
        "ok": True,
        "status": "NOTIFY_CASCADE_STARTED" if advance.status == "advanced" else advance.status.upper(),
        "live_execution": True,
        "slice_key": slice_key,
        "dispatch_id": dispatch_id,
        "offer_id": str(offer_id) if offer_id else None,
        "notifications": notifications,
        "cascade": cascade,
        "advance_status": advance.status,
        "advance_message": advance.message,
        "sms_dry_run": settings.SMS_DRY_RUN,
        "staged_at_utc": _utc_now_iso(),
    }
    if persist:
        result["log_path"] = str(_persist_notify_log(result).relative_to(_REPO_ROOT)).replace("\\", "/")
    return result


def run_backup_cascade_worker_tick(db: Session) -> list[BackupCascadeAdvanceResult]:
    if not settings.SNIPER_CASCADE_WORKER_ENABLED or not settings.SNIPER_CASCADE_ENABLED:
        return []

    store = _load_active_store()
    results: list[BackupCascadeAdvanceResult] = []
    for dispatch_id, session in list(store.get("cascades", {}).items()):
        if str(session.get("status") or "") != "ACTIVE":
            continue
        cascade = get_backup_cascade_status(db, dispatch_id)
        if not cascade.get("can_advance"):
            continue
        result = advance_backup_notify_cascade(db, dispatch_id, force=False, actor="backup_cascade_worker")
        if result.status == "advanced":
            results.append(result)
    return results
