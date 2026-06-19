"""Aggregate Maryland COMAR compliance snapshot for admin console."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ClinicianComplianceDocument, FacilityCrisisSignal, MarylandProvider
from app.services.compliance_monitor import provider_dispatch_eligible
from app.services.postgis_geo import describe_postgis_status


def build_compliance_overview(db: Session, *, limit: int = 100) -> dict:
    now = datetime.now(timezone.utc)
    alert_days = settings.COMPLIANCE_ALERT_DAYS

    total_providers = db.query(func.count(MarylandProvider.provider_id)).scalar() or 0
    dispatch_active = (
        db.query(func.count(MarylandProvider.provider_id))
        .filter(MarylandProvider.dispatch_status == "ACTIVE")
        .scalar()
        or 0
    )
    dispatch_suspended = (
        db.query(func.count(MarylandProvider.provider_id))
        .filter(MarylandProvider.dispatch_status == "SUSPENDED")
        .scalar()
        or 0
    )
    alert_cutoff = now + timedelta(days=alert_days)
    expiring_document_alerts = (
        db.query(func.count(ClinicianComplianceDocument.document_id))
        .filter(
            ClinicianComplianceDocument.expires_on.isnot(None),
            ClinicianComplianceDocument.expires_on > now,
            ClinicianComplianceDocument.expires_on <= alert_cutoff,
        )
        .scalar()
        or 0
    )
    crisis_signal_count = db.query(func.count(FacilityCrisisSignal.signal_id)).scalar() or 0

    providers = (
        db.query(MarylandProvider)
        .order_by(MarylandProvider.applied_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    provider_rows: list[dict] = []
    for provider in providers:
        documents = (
            db.query(ClinicianComplianceDocument)
            .filter(ClinicianComplianceDocument.provider_id == provider.provider_id)
            .all()
        )
        expiring = 0
        for row in documents:
            if row.expires_on is None:
                continue
            days_left = (row.expires_on - now).days
            if 0 < days_left <= alert_days:
                expiring += 1
        provider_rows.append(
            {
                "provider_id": provider.provider_id,
                "full_name": provider.full_name,
                "credential_type": provider.credential_type,
                "license_status": provider.license_status,
                "dispatch_status": provider.dispatch_status,
                "dispatch_eligible": provider_dispatch_eligible(db, provider),
                "expiring_documents": expiring,
                "license_expires_on": provider.license_expires_on.isoformat()
                if provider.license_expires_on
                else None,
            }
        )

    postgis = describe_postgis_status(db)

    return {
        "total_providers": int(total_providers),
        "dispatch_active": int(dispatch_active),
        "dispatch_suspended": int(dispatch_suspended),
        "expiring_document_alerts": int(expiring_document_alerts),
        "crisis_signal_count": int(crisis_signal_count),
        "geo_match_radius_miles": float(settings.GEO_MATCH_RADIUS_MILES),
        "postgis_enabled": postgis["postgis_enabled"],
        "postgis_version": postgis["postgis_version"],
        "dry_run_flags": {
            "mbon": settings.MBON_VERIFY_DRY_RUN,
            "oig": settings.OIG_SCREEN_DRY_RUN,
            "judiciary": settings.MD_JUDICIARY_DRY_RUN,
            "job_board": settings.JOB_BOARD_SCRAPE_DRY_RUN,
            "vms_ingest": settings.VMS_INGEST_DRY_RUN,
        },
        "providers": provider_rows,
    }
