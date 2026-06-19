"""Production ops dashboard — unified worker, metrics, launch, and scraper signals (step 137)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.cascade_worker import cascade_worker_status
from app.services.compliance_scheduler import compliance_scheduler_status
from app.services.integrations import integration_snapshot
from app.services.live_scraper_probes import probe_all_live_scrapers
from app.services.live_scrapers import live_scraper_snapshot, live_scrapers_summary
from app.services.maryland_launch_capstone import build_maryland_launch_capstone
from app.services.ops_metrics import get_ops_metrics, list_ops_audit_events
from app.services.staffing_scheduler import staffing_scheduler_status

PRODUCTION_OPS_DASHBOARD_JSON_FILENAME = "offercare-production-ops-dashboard.json"

_OPS_DEPLOY_ITEM_IDS = (
    "staffing_scheduler",
    "compliance_scheduler",
    "live_scrapers",
    "maryland_production",
    "live_sms_production",
    "maryland_launch_capstone",
)


def _serialize_audit_event(row) -> dict:
    return {
        "event_id": str(row.event_id),
        "event_type": row.event_type,
        "actor": row.actor,
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id) if row.entity_id else None,
        "summary": row.summary,
        "metadata_json": row.metadata_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _worker_check(
    *,
    check_id: str,
    title: str,
    enabled: bool,
    running: bool,
    detail_ready: str,
    detail_disabled: str,
    action_disabled: str,
) -> dict:
    if not enabled:
        return {
            "id": check_id,
            "title": title,
            "status": "blocked",
            "detail": detail_disabled,
            "action": action_disabled,
        }
    if running:
        return {
            "id": check_id,
            "title": title,
            "status": "ready",
            "detail": detail_ready,
            "action": None,
        }
    return {
        "id": check_id,
        "title": title,
        "status": "warning",
        "detail": f"{detail_ready} — background loop not running (manual ticks still available)",
        "action": "Restart API process or confirm worker task started in lifespan",
    }


def build_production_ops_dashboard(
    db: Session,
    *,
    include_probes: bool = False,
    audit_limit: int = 25,
) -> dict:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db.rollback()

    metrics = get_ops_metrics(db)
    cascade = cascade_worker_status()
    staffing = staffing_scheduler_status()
    compliance = compliance_scheduler_status()
    scraper_summary = live_scrapers_summary()
    scraper_channels = live_scraper_snapshot()
    integrations = integration_snapshot()
    launch = build_maryland_launch_capstone(db)
    launch_summary = launch["summary"]

    checks: list[dict] = []
    checks.append(
        {
            "id": "database",
            "title": "PostgreSQL",
            "status": "ready" if db_ok else "blocked",
            "detail": "PostgreSQL connection OK" if db_ok else "Database unreachable",
            "action": None if db_ok else "Start PostgreSQL or run docker compose up db",
        }
    )
    checks.append(
        _worker_check(
            check_id="cascade_worker",
            title="Cascade worker",
            enabled=cascade.enabled and cascade.cascade_enabled,
            running=cascade.running,
            detail_ready=f"Cascade worker enabled · interval {cascade.interval_seconds}s",
            detail_disabled="SNIPER_CASCADE_WORKER_ENABLED or SNIPER_CASCADE_ENABLED is false",
            action_disabled="Set SNIPER_CASCADE_WORKER_ENABLED=true and SNIPER_CASCADE_ENABLED=true",
        )
    )
    checks.append(
        _worker_check(
            check_id="staffing_vms_worker",
            title="VMS poll worker",
            enabled=staffing.vms_enabled,
            running=staffing.vms_running,
            detail_ready=f"VMS poll every {staffing.vms_interval_seconds // 60}m",
            detail_disabled="STAFFING_VMS_WORKER_ENABLED=false",
            action_disabled="Set STAFFING_VMS_WORKER_ENABLED=true",
        )
    )
    checks.append(
        _worker_check(
            check_id="staffing_job_board_worker",
            title="Job board worker",
            enabled=staffing.job_board_enabled,
            running=staffing.job_board_running,
            detail_ready=f"Job board scan every {staffing.job_board_interval_seconds // 3600}h",
            detail_disabled="STAFFING_JOB_BOARD_WORKER_ENABLED=false",
            action_disabled="Set STAFFING_JOB_BOARD_WORKER_ENABLED=true",
        )
    )
    checks.append(
        _worker_check(
            check_id="compliance_monitor_worker",
            title="Compliance monitor worker",
            enabled=compliance.enabled,
            running=compliance.running,
            detail_ready=f"Compliance sweep every {compliance.interval_seconds // 3600}h",
            detail_disabled="COMPLIANCE_MONITOR_WORKER_ENABLED=false",
            action_disabled="Set COMPLIANCE_MONITOR_WORKER_ENABLED=true",
        )
    )

    if scraper_summary["all_live"]:
        scraper_status = "ready"
        scraper_detail = "All five credentialing and ingest scrapers are live-ready"
        scraper_action = None
    elif scraper_summary["live_ready_count"] > 0:
        scraper_status = "warning"
        scraper_detail = (
            f"{scraper_summary['live_ready_count']}/{scraper_summary['total_channels']} "
            f"scraper channels live · {scraper_summary['dry_run_count']} still dry-run"
        )
        scraper_action = "Admin → Integrations → Probe live scrapers and flip *_DRY_RUN=false"
    else:
        scraper_status = "blocked"
        scraper_detail = f"All {scraper_summary['total_channels']} scraper channels in dry-run"
        scraper_action = "Configure LIVE_SCRAPER_GATEWAY_BASE_URL and disable dry-run flags"
    checks.append(
        {
            "id": "live_scrapers",
            "title": "Live scrapers",
            "status": scraper_status,
            "detail": scraper_detail,
            "action": scraper_action,
        }
    )

    if launch["launch_ready"]:
        launch_status = "ready"
        launch_detail = "Maryland launch capstone green"
        launch_action = None
    elif launch_summary["blocked"] > 0:
        launch_status = "blocked"
        launch_detail = f"Maryland launch blocked — {launch_summary['blocked']} blocker(s)"
        launch_action = "Admin → Deploy → Maryland launch capstone"
    else:
        launch_status = "warning"
        launch_detail = "Maryland launch partial — finish production runbooks"
        launch_action = "Complete Maryland production and live SMS runbooks"
    checks.append(
        {
            "id": "maryland_launch",
            "title": "Maryland launch readiness",
            "status": launch_status,
            "detail": launch_detail,
            "action": launch_action,
        }
    )

    twilio = integrations["twilio"]
    if twilio["live_ready"]:
        sms_status = "ready"
        sms_detail = "Twilio live SMS ready"
        sms_action = None
    elif twilio["configured"]:
        sms_status = "warning"
        sms_detail = "Twilio configured but still in dry-run or missing HTTPS webhook"
        sms_action = "Set SMS_DRY_RUN=false and PUBLIC_BASE_URL"
    else:
        sms_status = "blocked"
        sms_detail = "Twilio credentials not configured"
        sms_action = "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER"
    checks.append(
        {
            "id": "twilio_live_sms",
            "title": "Twilio live SMS",
            "status": sms_status,
            "detail": sms_detail,
            "action": sms_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")
    production_ops_ready = blocked == 0 and launch["launch_ready"] and scraper_summary["all_live"]

    scraper_probes: list[dict] = []
    if include_probes:
        scraper_probes = [asdict(row) for row in probe_all_live_scrapers()]
        if scraper_summary["all_live"] and scraper_probes:
            probes_ok = all(row["status"] == "LIVE_OK" for row in scraper_probes)
            checks.append(
                {
                    "id": "scraper_probes",
                    "title": "Live scraper probes",
                    "status": "ready" if probes_ok else "warning",
                    "detail": (
                        f"{sum(1 for row in scraper_probes if row['status'] == 'LIVE_OK')}/"
                        f"{len(scraper_probes)} channels LIVE_OK"
                    ),
                    "action": None if probes_ok else "Admin → Integrations → Probe live scrapers",
                }
            )
            blocked = sum(1 for row in checks if row["status"] == "blocked")
            warnings = sum(1 for row in checks if row["status"] == "warning")
            ready = sum(1 for row in checks if row["status"] == "ready")
            if probes_ok and production_ops_ready:
                production_ops_ready = blocked == 0

    workers_enabled = sum(
        1
        for enabled in (
            cascade.enabled and cascade.cascade_enabled,
            staffing.vms_enabled,
            staffing.job_board_enabled,
            compliance.enabled,
        )
        if enabled
    )
    workers_running = sum(
        1
        for running in (
            cascade.running,
            staffing.vms_running,
            staffing.job_board_running,
            compliance.running,
        )
        if running
    )

    audit_rows = list_ops_audit_events(db, limit=audit_limit)

    steps = [
        "Admin → Production ops dashboard → Refresh all production signals",
        "Confirm all four background workers are enabled and running",
        "Probe live scrapers — all five channels should return LIVE_OK",
        "Run cascade, VMS poll, job board, and compliance manual ticks to verify schedulers",
        "Review audit log for SHIFT_NOTIFY, SHIFT_LOCK, VMS_WORKER_TICK, and COMPLIANCE_MONITOR_TICK events",
        "Confirm Maryland launch capstone and Twilio live SMS checks are green",
        "Monitor lock rate and SMS volume in ops metrics during live shifts",
        "Export production ops dashboard JSON for nightly ops sign-off",
    ]

    return {
        "production_ops_ready": production_ops_ready,
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "database_ok": db_ok,
            "workers_enabled_count": workers_enabled,
            "workers_running_count": workers_running,
            "live_scrapers_live_count": scraper_summary["live_ready_count"],
            "live_scrapers_total": scraper_summary["total_channels"],
            "live_scrapers_all_live": scraper_summary["all_live"],
            "maryland_launch_ready": launch["launch_ready"],
            "maryland_production_ready": launch["maryland_production_ready"],
            "twilio_sms_production_ready": launch["twilio_sms_production_ready"],
            "live_sms_ready": launch["live_sms_ready"],
            "lock_rate": metrics["lock_rate"],
            "audit_events_24h": metrics["audit_events_24h"],
            "total_sms_sent": metrics["total_sms_sent"],
            "open_shifts": metrics["open_shifts"],
            "locked_shifts": metrics["locked_shifts"],
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "health": {
            "database": "ok" if db_ok else "error",
            "cascade_worker_enabled": cascade.enabled,
            "staffing_vms_worker_enabled": staffing.vms_enabled,
            "staffing_job_board_worker_enabled": staffing.job_board_enabled,
            "compliance_monitor_worker_enabled": compliance.enabled,
            "live_scrapers_all_live": scraper_summary["all_live"],
            "live_scraper_gateway_configured": bool(str(settings.LIVE_SCRAPER_GATEWAY_BASE_URL or "").strip()),
            "maryland_launch_ready": launch["launch_ready"],
            "production_ops_ready": production_ops_ready,
        },
        "metrics": metrics,
        "workers": {
            "cascade": asdict(cascade),
            "staffing": asdict(staffing),
            "compliance": asdict(compliance),
        },
        "integrations": integrations,
        "live_scrapers": {
            "summary": scraper_summary,
            "channels": scraper_channels,
        },
        "launch": {
            "launch_ready": launch["launch_ready"],
            "maryland_production_ready": launch["maryland_production_ready"],
            "twilio_sms_production_ready": launch["twilio_sms_production_ready"],
            "live_sms_ready": launch["live_sms_ready"],
        },
        "scraper_probes": scraper_probes,
        "audit_events": [_serialize_audit_event(row) for row in audit_rows],
    }


def refresh_production_ops_dashboard(
    db: Session,
    *,
    probe_scrapers: bool = True,
    audit_limit: int = 25,
) -> dict:
    return build_production_ops_dashboard(
        db,
        include_probes=probe_scrapers,
        audit_limit=audit_limit,
    )


def build_production_ops_dashboard_json(db: Session, *, include_probes: bool = False) -> dict:
    snapshot = build_production_ops_dashboard(db, include_probes=include_probes)
    return {
        "filename": PRODUCTION_OPS_DASHBOARD_JSON_FILENAME,
        "content": json.dumps(snapshot, indent=2),
    }


def as_production_ops_dashboard_response(snapshot: dict):
    from app.schemas import OpsMetricsResponse, ProductionOpsDashboardResponse

    return ProductionOpsDashboardResponse(
        production_ops_ready=snapshot["production_ops_ready"],
        summary=snapshot["summary"],
        checks=snapshot["checks"],
        steps=snapshot["steps"],
        health=snapshot["health"],
        metrics=OpsMetricsResponse.model_validate(snapshot["metrics"]),
        workers=snapshot["workers"],
        integrations=snapshot["integrations"],
        live_scrapers=snapshot["live_scrapers"],
        launch=snapshot["launch"],
        scraper_probes=snapshot.get("scraper_probes") or [],
        audit_events=snapshot.get("audit_events") or [],
    )
