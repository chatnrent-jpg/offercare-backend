"""Manus daily work queue — who VettedMe needs vetted next."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ManusVettingRun, MarylandProvider
from app.services.vetted_status import (
    ALL_VETTED_STATUSES,
    VETTED_ACTION_NEEDED,
    VETTED_BLOCKED,
    VETTED_CLEAR,
    VETTED_EXPIRING,
    compute_vetted_status,
)

DEFAULT_MANUS_CHECKS = ("MBON", "OIG", "JUDICIARY")

_PRIORITY_RANK = {
    VETTED_BLOCKED: 0,
    VETTED_EXPIRING: 1,
    VETTED_ACTION_NEEDED: 2,
    VETTED_CLEAR: 3,
}


def _base_url() -> str:
    configured = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    return configured or "http://127.0.0.1:8000"


def build_manus_integration_config() -> dict:
    base = _base_url()
    prefix = f"{base}/api/vettedme/manus"
    return {
        "product": settings.PROJECT_NAME,
        "tagline": settings.VETTED_TAGLINE,
        "base_url": base,
        "auth_header": "X-Manus-Key",
        "required_checks": list(DEFAULT_MANUS_CHECKS),
        "endpoints": {
            "config": f"{prefix}/config",
            "work_queue": f"{prefix}/work-queue",
            "provider_work_order": f"{prefix}/providers/{{provider_id}}",
            "submit_run": f"{prefix}/run",
            "batch_submit": f"{prefix}/batch",
        },
        "limits": {
            "work_queue_default": settings.MANUS_WORK_QUEUE_DEFAULT_LIMIT,
            "stale_clear_days": settings.MANUS_STALE_CLEAR_DAYS,
            "min_rerun_hours": settings.MANUS_MIN_RERUN_HOURS,
        },
        "operator_note": "Manus acts. VettedMe decides. Submit evidence; do not override computed status.",
    }


def _last_manus_runs(db: Session) -> dict[UUID, datetime]:
    rows = (
        db.query(ManusVettingRun.provider_id, func.max(ManusVettingRun.applied_at))
        .filter(ManusVettingRun.provider_id.isnot(None), ManusVettingRun.status == "APPLIED")
        .group_by(ManusVettingRun.provider_id)
        .all()
    )
    return {provider_id: applied_at for provider_id, applied_at in rows if applied_at is not None}


def _priority_label(rank: int) -> str:
    if rank <= 0:
        return "CRITICAL"
    if rank == 1:
        return "HIGH"
    if rank == 2:
        return "MEDIUM"
    return "LOW"


def _required_checks(provider: MarylandProvider) -> list[dict]:
    checks: list[dict] = []
    for check_type in DEFAULT_MANUS_CHECKS:
        entry = {
            "check_type": check_type,
            "description": _check_description(check_type),
        }
        if check_type == "MBON":
            entry["lookup"] = {
                "license_number": provider.md_license_number,
                "full_name": provider.full_name,
                "credential_type": provider.credential_type,
                "state": provider.state,
            }
        elif check_type == "OIG":
            entry["lookup"] = {
                "full_name": provider.full_name,
                "npi_number": provider.npi_number,
            }
        elif check_type in {"JUDICIARY", "MD_JUDICIARY"}:
            entry["lookup"] = {
                "full_name": provider.full_name,
                "license_number": provider.md_license_number,
                "state": provider.state,
            }
        checks.append(entry)
    return checks


def _check_description(check_type: str) -> str:
    mapping = {
        "MBON": "Verify Maryland Board of Nursing license is active and matches profile.",
        "OIG": "Search OIG LEIE exclusions for name and NPI.",
        "JUDICIARY": "Search Maryland judiciary / disciplinary records for open cases.",
    }
    return mapping.get(check_type, "Run credential verification check.")


def _needs_vetting(
    provider: MarylandProvider,
    *,
    status: str,
    last_manus_at: datetime | None,
    now: datetime,
    queue: str,
) -> tuple[bool, str | None]:
    stale_after = now - timedelta(days=settings.MANUS_STALE_CLEAR_DAYS)
    rerun_after = now - timedelta(hours=settings.MANUS_MIN_RERUN_HOURS)

    if queue == "all":
        if (
            last_manus_at
            and last_manus_at > rerun_after
            and status not in {VETTED_BLOCKED, VETTED_EXPIRING}
        ):
            return False, None
        return True, f"Included in full Manus sweep ({status})"

    if queue == "blocked" and status != VETTED_BLOCKED:
        return False, None
    if queue == "expiring" and status != VETTED_EXPIRING:
        return False, None
    if queue == "action_needed" and status != VETTED_ACTION_NEEDED:
        return False, None
    if queue == "stale_clear":
        if status != VETTED_CLEAR:
            return False, None
        if last_manus_at is None or last_manus_at <= stale_after:
            return True, "CLEAR profile due for periodic re-verification"
        return False, None

    if status in {VETTED_BLOCKED, VETTED_EXPIRING, VETTED_ACTION_NEEDED}:
        if last_manus_at and last_manus_at > rerun_after and status != VETTED_BLOCKED:
            return False, None
        return True, f"Status {status} requires autonomous vetting"

    if status == VETTED_CLEAR:
        if last_manus_at is None:
            return True, "CLEAR profile never vetted by Manus"
        if last_manus_at <= stale_after:
            return True, "CLEAR profile due for periodic re-verification"
        return False, None

    return False, None


def build_manus_work_queue(
    db: Session,
    *,
    limit: int | None = None,
    queue: str = "due",
) -> dict:
    now = datetime.now(timezone.utc)
    max_items = min(limit or settings.MANUS_WORK_QUEUE_DEFAULT_LIMIT, 200)
    last_runs = _last_manus_runs(db)
    providers = db.query(MarylandProvider).all()

    candidates: list[dict] = []
    skipped_recent = 0

    for provider in providers:
        status = compute_vetted_status(db, provider)
        last_manus_at = last_runs.get(provider.provider_id)
        include, reason = _needs_vetting(
            provider,
            status=status,
            last_manus_at=last_manus_at,
            now=now,
            queue=queue,
        )
        if not include:
            if (
                status in {VETTED_EXPIRING, VETTED_ACTION_NEEDED}
                and last_manus_at
                and last_manus_at > now - timedelta(hours=settings.MANUS_MIN_RERUN_HOURS)
            ):
                skipped_recent += 1
            continue

        rank = _PRIORITY_RANK.get(status, 99)
        candidates.append(
            {
                "provider_id": str(provider.provider_id),
                "full_name": provider.full_name,
                "credential_type": provider.credential_type,
                "state": provider.state,
                "npi_number": provider.npi_number,
                "md_license_number": provider.md_license_number,
                "email": provider.email,
                "vetted_status": status,
                "license_status": provider.license_status,
                "priority_rank": rank,
                "priority": _priority_label(rank),
                "reason": reason,
                "last_manus_applied_at": last_manus_at.isoformat() if last_manus_at else None,
                "required_checks": [row["check_type"] for row in _required_checks(provider)],
                "work_order_url": f"{_base_url()}/api/vettedme/manus/providers/{provider.provider_id}",
                "submit_url": f"{_base_url()}/api/vettedme/manus/run",
            }
        )

    candidates.sort(
        key=lambda row: (
            row["priority_rank"],
            row["last_manus_applied_at"] is not None,
            row["last_manus_applied_at"] or "",
        )
    )
    selected = candidates[:max_items]

    status_breakdown = {status: 0 for status in ALL_VETTED_STATUSES}
    for row in candidates:
        status_breakdown[row["vetted_status"]] = status_breakdown.get(row["vetted_status"], 0) + 1

    return {
        "generated_at": now.isoformat(),
        "queue": queue,
        "total_due": len(candidates),
        "returned": len(selected),
        "skipped_recent_runs": skipped_recent,
        "status_breakdown_due": status_breakdown,
        "items": selected,
        "submit_batch_url": f"{_base_url()}/api/vettedme/manus/batch",
        "next_steps": [
            "Fetch one work order per provider.",
            "Run MBON, OIG, and JUDICIARY checks.",
            "POST results to submit_url with header X-Manus-Key.",
        ],
    }


def build_manus_provider_work_order(db: Session, provider_id: UUID) -> dict:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    status = compute_vetted_status(db, provider)
    last_runs = _last_manus_runs(db)
    last_manus_at = last_runs.get(provider.provider_id)
    rank = _PRIORITY_RANK.get(status, 99)

    return {
        "provider_id": str(provider.provider_id),
        "full_name": provider.full_name,
        "email": provider.email,
        "phone_number": provider.phone_number,
        "credential_type": provider.credential_type,
        "state": provider.state,
        "npi_number": provider.npi_number,
        "md_license_number": provider.md_license_number,
        "license_status": provider.license_status,
        "license_expires_on": provider.license_expires_on.isoformat() if provider.license_expires_on else None,
        "vetted_status": status,
        "priority": _priority_label(rank),
        "last_manus_applied_at": last_manus_at.isoformat() if last_manus_at else None,
        "required_checks": _required_checks(provider),
        "submit": {
            "method": "POST",
            "url": f"{_base_url()}/api/vettedme/manus/run",
            "headers": {"X-Manus-Key": "<MANUS_API_KEY>", "Content-Type": "application/json"},
            "body_template": {
                "run_id": f"manus-{provider.provider_id}-{{timestamp}}",
                "provider_id": str(provider.provider_id),
                "summary": "Autonomous credential vetting run",
                "checks": [
                    {"check_type": "MBON", "result": "PASS", "notes": "Evidence here"},
                    {"check_type": "OIG", "result": "CLEAR", "notes": "Evidence here"},
                    {"check_type": "JUDICIARY", "result": "PASS", "notes": "Evidence here"},
                ],
            },
        },
    }
