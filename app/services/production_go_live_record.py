"""Production go-live record — immutable sealed launch archive (step 140)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.deploy_walkthrough import DEPLOY_EXPORT_ZIP_FILENAME
from app.services.live_scrapers import live_scrapers_summary
from app.services.maryland_launch_capstone import build_maryland_launch_capstone
from app.services.maryland_production_runbook import build_maryland_production_runbook
from app.services.production_launch_ceremony import (
    PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
    PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME,
    build_production_launch_ceremony,
    run_production_launch_ceremony,
)
from app.services.production_ops_dashboard import build_production_ops_dashboard
from app.services.production_perfection_capstone import (
    PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
    build_production_perfection_capstone,
)
from app.services.twilio_sms_production_runbook import build_twilio_sms_production_runbook

PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME = "offercare-production-go-live-record.json"

_GO_LIVE_BUNDLE_ARTIFACTS = (
    "offercare-deploy-checklist.json",
    "offercare-deploy-checklist.csv",
    "offercare-demo-walkthrough.md",
    "offercare-demo-gates.json",
    "offercare-demo-gates.txt",
    "offercare-demo-status.json",
    "offercare-demo-status.csv",
    "offercare-maryland-production-runbook.json",
    "offercare-twilio-sms-production-runbook.json",
    "offercare-maryland-launch-capstone.json",
    "offercare-production-ops-dashboard.json",
    "offercare-production-perfection-capstone.json",
    PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME,
    PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
    PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
    "README.txt",
)

_SEALED_LAUNCH_RECORD: dict | None = None


def reset_sealed_launch_record_for_tests() -> None:
    """Clear the in-process sealed record (tests only)."""
    global _SEALED_LAUNCH_RECORD
    _SEALED_LAUNCH_RECORD = None


def get_sealed_launch_record() -> dict | None:
    return _SEALED_LAUNCH_RECORD


def _build_health_snapshot(db: Session) -> dict:
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    status = "ok" if database == "ok" else "degraded"
    scraper_summary = live_scrapers_summary()
    md_production = build_maryland_production_runbook(db)
    sms_production = build_twilio_sms_production_runbook(db)
    launch_capstone = build_maryland_launch_capstone(db)
    ops_dashboard = build_production_ops_dashboard(db)
    perfection_capstone = build_production_perfection_capstone(db)
    launch_ceremony = build_production_launch_ceremony(db)
    return {
        "status": status,
        "database": database,
        "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
        "security_headers_enabled": settings.SECURITY_HEADERS_ENABLED,
        "cascade_worker_enabled": settings.SNIPER_CASCADE_WORKER_ENABLED,
        "staffing_vms_worker_enabled": settings.STAFFING_VMS_WORKER_ENABLED,
        "staffing_job_board_worker_enabled": settings.STAFFING_JOB_BOARD_WORKER_ENABLED,
        "compliance_monitor_worker_enabled": settings.COMPLIANCE_MONITOR_WORKER_ENABLED,
        "live_scrapers_all_live": scraper_summary["all_live"],
        "live_scraper_gateway_configured": bool(str(settings.LIVE_SCRAPER_GATEWAY_BASE_URL or "").strip()),
        "maryland_production_ready": md_production["production_ready"],
        "live_sms_ready": sms_production["live_sms_ready"],
        "twilio_sms_production_ready": sms_production["production_ready"],
        "maryland_launch_ready": launch_capstone["launch_ready"],
        "production_ops_ready": ops_dashboard["production_ops_ready"],
        "production_perfection_ready": perfection_capstone["production_perfection_ready"],
        "production_launch_ceremony_ready": launch_ceremony["launch_ceremony_ready"],
        "production_go_live_record_ready": _SEALED_LAUNCH_RECORD is not None
        and bool(_SEALED_LAUNCH_RECORD.get("seal_ok")),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def build_production_go_live_record(db: Session) -> dict:
    ceremony = build_production_launch_ceremony(db)
    ceremony_summary = ceremony["summary"]
    sealed = _SEALED_LAUNCH_RECORD
    bundle_file_count = len(_GO_LIVE_BUNDLE_ARTIFACTS)

    checks: list[dict] = []

    if ceremony["launch_ceremony_ready"]:
        ceremony_check_status = "ready"
        ceremony_check_detail = "Launch ceremony green — ready to seal immutable go-live record"
        ceremony_check_action = None
    elif ceremony_summary["blocked"] > 0:
        ceremony_check_status = "blocked"
        ceremony_check_detail = (
            f"Launch ceremony blocked — {ceremony_summary['blocked']} blocker(s)"
        )
        ceremony_check_action = "Admin → Production launch ceremony → Run launch ceremony after perfection is green"
    else:
        ceremony_check_status = "warning"
        ceremony_check_detail = "Launch ceremony partial — complete stakeholder sign-off before sealing"
        ceremony_check_action = "Admin → Production launch ceremony → Run launch ceremony"
    checks.append(
        {
            "id": "production_launch_ceremony",
            "title": "Production launch ceremony",
            "status": ceremony_check_status,
            "detail": ceremony_check_detail,
            "action": ceremony_check_action,
        }
    )

    if sealed and sealed.get("seal_ok"):
        seal_status = "ready"
        seal_detail = (
            f"Go-live record sealed at {sealed.get('sealed_at', '—')} — immutable launch archive"
        )
        seal_action = None
    elif sealed:
        seal_status = "blocked"
        seal_detail = "Go-live record seal attempted but failed — re-run seal after ceremony is green"
        seal_action = "Admin → Production go-live record → Seal launch record"
    elif ceremony["launch_ceremony_ready"]:
        seal_status = "warning"
        seal_detail = "Go-live record not yet sealed — run Seal launch record to archive ceremony + health snapshot"
        seal_action = "Admin → Production go-live record → Seal launch record"
    else:
        seal_status = "blocked"
        seal_detail = "Go-live record blocked — launch ceremony must be green before sealing"
        seal_action = "Complete launch ceremony first, then seal go-live record"
    checks.append(
        {
            "id": "production_go_live_record",
            "title": "Production go-live record",
            "status": seal_status,
            "detail": seal_detail,
            "action": seal_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    production_go_live_record_ready = bool(sealed and sealed.get("seal_ok"))

    steps = [
        "Confirm production_launch_ceremony_ready is true on /health and Admin ceremony panel",
        "Admin → Production launch ceremony → Run launch ceremony — perfection check + sign-off snapshot",
        "Admin → Production go-live record → Seal launch record — archives ceremony run + health snapshot",
        "Download sealed go-live record JSON for compliance audit trail and launch archive",
        "Export deploy bundle (.zip) — full 16-file production archive including sealed go-live record",
        "Verify production_go_live_record_ready on /health after seal completes",
        "Share worker landing /join URL with Maryland operations for go-live communications",
        "Retain sealed go-live record alongside ceremony markdown for executive launch sign-off",
    ]

    record = {
        "production_go_live_record_ready": production_go_live_record_ready,
        "launch_ceremony_ready": ceremony["launch_ceremony_ready"],
        "production_perfection_ready": ceremony["production_perfection_ready"],
        "production_ops_ready": ceremony["production_ops_ready"],
        "maryland_launch_ready": ceremony["maryland_launch_ready"],
        "sealed": sealed is not None,
        "immutable": bool(sealed and sealed.get("immutable")),
        "record_id": sealed.get("record_id") if sealed else None,
        "sealed_at": sealed.get("sealed_at") if sealed else None,
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "launch_ceremony_ready": ceremony["launch_ceremony_ready"],
            "production_perfection_ready": ceremony["production_perfection_ready"],
            "production_ops_ready": ceremony["production_ops_ready"],
            "maryland_launch_ready": ceremony["maryland_launch_ready"],
            "live_scrapers_all_live": ceremony_summary.get("live_scrapers_all_live"),
            "deploy_bundle_file_count": bundle_file_count,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "perfection_capstone_filename": PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
            "ceremony_json_filename": PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
            "go_live_record_filename": PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "launch_urls": ceremony["launch_urls"],
        "bundle_artifacts": list(_GO_LIVE_BUNDLE_ARTIFACTS),
        "production_launch_ceremony": ceremony,
        "sealed_record": sealed,
        "health_snapshot": sealed.get("health_snapshot") if sealed else _build_health_snapshot(db),
    }
    return record


def build_production_go_live_record_json(db: Session) -> dict:
    record = build_production_go_live_record(db)
    export_payload = {
        "production_go_live_record_ready": record["production_go_live_record_ready"],
        "launch_ceremony_ready": record["launch_ceremony_ready"],
        "sealed": record["sealed"],
        "immutable": record["immutable"],
        "record_id": record["record_id"],
        "sealed_at": record["sealed_at"],
        "summary": record["summary"],
        "checks": record["checks"],
        "launch_urls": record["launch_urls"],
        "bundle_artifacts": record["bundle_artifacts"],
        "health_snapshot": record["health_snapshot"],
        "ceremony_run": (record["sealed_record"] or {}).get("ceremony_run"),
        "production_launch_ceremony": record["production_launch_ceremony"],
    }
    return {
        "filename": PRODUCTION_GO_LIVE_RECORD_JSON_FILENAME,
        "content": json.dumps(export_payload, indent=2),
    }


def seal_production_go_live_record(
    db: Session,
    *,
    phone_number: str | None = None,
    probe_scrapers: bool = True,
) -> dict:
    global _SEALED_LAUNCH_RECORD

    if _SEALED_LAUNCH_RECORD is not None and _SEALED_LAUNCH_RECORD.get("seal_ok"):
        record = build_production_go_live_record(db)
        return {
            "ok": True,
            "already_sealed": True,
            "production_go_live_record_ready": True,
            "launch_ceremony_ready": record["launch_ceremony_ready"],
            "record_id": _SEALED_LAUNCH_RECORD["record_id"],
            "sealed_at": _SEALED_LAUNCH_RECORD["sealed_at"],
            "deploy_bundle_filename": record["summary"]["deploy_bundle_filename"],
            "deploy_bundle_file_count": record["summary"]["deploy_bundle_file_count"],
            "facility_name": _SEALED_LAUNCH_RECORD.get("facility_name"),
            "placement_id": _SEALED_LAUNCH_RECORD.get("placement_id"),
            "message": (
                f"Go-live record already sealed at {_SEALED_LAUNCH_RECORD['sealed_at']} "
                f"(record {_SEALED_LAUNCH_RECORD['record_id']})"
            ),
        }

    ceremony_result = run_production_launch_ceremony(
        db,
        phone_number=phone_number,
        probe_scrapers=probe_scrapers,
    )
    health_snapshot = _build_health_snapshot(db)
    sealed_at = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    seal_ok = bool(ceremony_result["ok"])

    _SEALED_LAUNCH_RECORD = {
        "record_id": record_id,
        "sealed_at": sealed_at,
        "immutable": True,
        "seal_ok": seal_ok,
        "ceremony_run": ceremony_result,
        "health_snapshot": health_snapshot,
        "facility_name": ceremony_result.get("facility_name"),
        "placement_id": ceremony_result.get("placement_id"),
    }

    record = build_production_go_live_record(db)

    if seal_ok:
        message = (
            "Production go-live record sealed — ceremony run archived with health snapshot "
            f"({record['summary']['deploy_bundle_file_count']} deploy bundle files)"
        )
    elif not ceremony_result["launch_ceremony_ready"]:
        message = "Go-live record seal failed — launch ceremony is not green"
    elif not ceremony_result["perfection_check_ok"]:
        message = ceremony_result.get("message") or "Go-live record seal failed — perfection check did not pass"
    else:
        message = "Go-live record seal failed"

    return {
        "ok": seal_ok,
        "already_sealed": False,
        "production_go_live_record_ready": seal_ok,
        "launch_ceremony_ready": ceremony_result["launch_ceremony_ready"],
        "perfection_check_ok": bool(ceremony_result["perfection_check_ok"]),
        "ceremony_run": ceremony_result,
        "health_snapshot": health_snapshot,
        "record_id": record_id,
        "sealed_at": sealed_at,
        "deploy_bundle_filename": record["summary"]["deploy_bundle_filename"],
        "deploy_bundle_file_count": record["summary"]["deploy_bundle_file_count"],
        "facility_name": ceremony_result.get("facility_name"),
        "placement_id": ceremony_result.get("placement_id"),
        "message": message,
    }
