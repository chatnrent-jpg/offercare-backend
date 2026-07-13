"""VettedMe admin dashboard aggregates."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CredentialSafetyAlert, ManusVettingRun, MarylandProvider, VettedMeAuditLog
from app.services.vetted_alerts import list_recent_alerts
from app.services.vetted_audit import list_vetted_audit
from app.services.vetted_status import ALL_VETTED_STATUSES, VETTED_CLEAR, sync_all_vetted_statuses


def _status_cache_stale(db: Session) -> bool:
    total = db.query(func.count(MarylandProvider.provider_id)).scalar() or 0
    if total == 0:
        return False
    unset = (
        db.query(func.count(MarylandProvider.provider_id))
        .filter(MarylandProvider.vetted_status_updated_at.is_(None))
        .scalar()
        or 0
    )
    return unset == total


def build_vettedme_dashboard(db: Session, *, provider_limit: int = 100) -> dict:
    if _status_cache_stale(db):
        sync_all_vetted_statuses(db, actor="dashboard")

    counts = {status: 0 for status in ALL_VETTED_STATUSES}
    rows = (
        db.query(MarylandProvider.vetted_status, func.count(MarylandProvider.provider_id))
        .group_by(MarylandProvider.vetted_status)
        .all()
    )
    for status, count in rows:
        key = str(status or "ACTION_NEEDED").upper()
        if key in counts:
            counts[key] = int(count)

    total = sum(counts.values())
    clear_rate = round((counts.get(VETTED_CLEAR, 0) / total) * 100, 1) if total else 0.0

    providers = (
        db.query(MarylandProvider)
        .order_by(MarylandProvider.vetted_status_updated_at.desc().nullslast(), MarylandProvider.applied_at.desc())
        .limit(min(provider_limit, 200))
        .all()
    )
    provider_rows = [
        {
            "provider_id": str(p.provider_id),
            "full_name": p.full_name,
            "credential_type": p.credential_type,
            "vetted_status": str(p.vetted_status or "ACTION_NEEDED").upper(),
            "license_status": p.license_status,
            "dispatch_status": p.dispatch_status,
            "vetted_status_updated_at": p.vetted_status_updated_at.isoformat()
            if p.vetted_status_updated_at
            else None,
        }
        for p in providers
    ]

    manus_runs = db.query(func.count(ManusVettingRun.run_id)).scalar() or 0
    manus_applied = (
        db.query(func.count(ManusVettingRun.run_id)).filter(ManusVettingRun.status == "APPLIED").scalar() or 0
    )
    audit_events = db.query(func.count(VettedMeAuditLog.audit_id)).scalar() or 0
    alerts_sent = db.query(func.count(CredentialSafetyAlert.alert_id)).scalar() or 0

    return {
        "product": settings.PROJECT_NAME,
        "tagline": settings.VETTED_TAGLINE,
        "safety_first": True,
        "total_providers": total,
        "clear_rate_percent": clear_rate,
        "status_counts": counts,
        "manus_runs_total": int(manus_runs),
        "manus_runs_applied": int(manus_applied),
        "audit_events_total": int(audit_events),
        "alerts_sent_total": int(alerts_sent),
        "providers": provider_rows,
        "recent_audit": list_vetted_audit(db, limit=15),
        "recent_alerts": list_recent_alerts(db, limit=15),
        "manus_webhook": "/api/vettedme/manus/run",
    }
