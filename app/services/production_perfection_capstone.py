"""Production perfection capstone — ops + launch + end-to-end smoke (step 138)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.maryland_launch_capstone import (
    build_maryland_launch_capstone,
    run_maryland_launch_smoke,
)
from app.services.production_ops_dashboard import (
    build_production_ops_dashboard,
    refresh_production_ops_dashboard,
)

PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME = "offercare-production-perfection-capstone.json"


def build_production_perfection_capstone(db: Session) -> dict:
    ops_dashboard = build_production_ops_dashboard(db)
    launch_capstone = build_maryland_launch_capstone(db)
    ops_summary = ops_dashboard["summary"]
    launch_summary = launch_capstone["summary"]

    checks: list[dict] = []

    if ops_dashboard["production_ops_ready"]:
        ops_status = "ready"
        ops_detail = "Production ops dashboard green — workers, scrapers, launch, and SMS signals ready"
        ops_action = None
    elif ops_summary["blocked"] > 0:
        ops_status = "blocked"
        ops_detail = (
            f"Production ops blocked — {ops_summary['blocked']} blocker(s), "
            f"{ops_summary['warnings']} warning(s)"
        )
        ops_action = "Admin → Production ops dashboard → Refresh all production signals"
    else:
        ops_status = "warning"
        ops_detail = (
            f"Production ops partial — {ops_summary['ready']} ready, "
            f"{ops_summary['warnings']} warning(s)"
        )
        ops_action = "Enable background workers, probe live scrapers, and confirm launch capstone"
    checks.append(
        {
            "id": "production_ops_dashboard",
            "title": "Production ops dashboard",
            "status": ops_status,
            "detail": ops_detail,
            "action": ops_action,
        }
    )

    if launch_capstone["launch_ready"]:
        launch_status = "ready"
        launch_detail = "Maryland launch capstone green — Maryland production and live SMS both ready"
        launch_action = None
    elif launch_summary["blocked"] > 0:
        launch_status = "blocked"
        launch_detail = (
            f"Maryland launch blocked — {launch_summary['blocked']} blocker(s), "
            f"{launch_summary['warnings']} warning(s)"
        )
        launch_action = "Admin → Deploy → Maryland launch capstone"
    else:
        launch_status = "warning"
        launch_detail = "Maryland launch partial — complete both production runbooks"
        launch_action = "Finish Maryland production and live SMS runbooks"
    checks.append(
        {
            "id": "maryland_launch_capstone",
            "title": "Maryland launch capstone",
            "status": launch_status,
            "detail": launch_detail,
            "action": launch_action,
        }
    )

    production_perfection_ready = (
        ops_dashboard["production_ops_ready"] and launch_capstone["launch_ready"]
    )
    if production_perfection_ready:
        perfection_status = "ready"
        perfection_detail = (
            "Production perfection green — ops dashboard and Maryland launch both ready for go-live"
        )
        perfection_action = None
    elif ops_status == "blocked" or launch_status == "blocked":
        perfection_status = "blocked"
        perfection_detail = "Production perfection blocked — resolve ops and launch blockers first"
        perfection_action = "Admin → Run production perfection check after both capstones are green"
    else:
        perfection_status = "warning"
        perfection_detail = "Production perfection partial — complete ops dashboard and launch capstone"
        perfection_action = "Admin → Production perfection → Run production perfection check"
    checks.append(
        {
            "id": "production_perfection",
            "title": "Production perfection",
            "status": perfection_status,
            "detail": perfection_detail,
            "action": perfection_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    steps = [
        "Confirm production ops dashboard is green — all workers enabled, scrapers live, launch and SMS ready",
        "Confirm Maryland launch capstone is green — Maryland production and Twilio live SMS runbooks complete",
        "Admin → Production perfection → Run production perfection check — refresh ops, probe scrapers, launch smoke",
        "Verify launch smoke locks Saint Jude demo shift via YES reply and ops refresh reports production_ops_ready",
        "Review audit log for VMS_WORKER_TICK, COMPLIANCE_MONITOR_TICK, SHIFT_NOTIFY, and SHIFT_LOCK events",
        "Export production perfection capstone JSON for final launch sign-off",
        "Deploy checklist production_perfection should flip to READY when ops and launch are both green",
        "Health endpoint production_perfection_ready should be true before public Maryland go-live",
    ]

    env_snippet = "\n".join(
        [
            launch_capstone["env_snippet"],
            "",
            "# Production ops workers (VettedCare step 138)",
            "SNIPER_CASCADE_WORKER_ENABLED=true",
            "SNIPER_CASCADE_ENABLED=true",
            "STAFFING_VMS_WORKER_ENABLED=true",
            "STAFFING_JOB_BOARD_WORKER_ENABLED=true",
            "COMPLIANCE_MONITOR_WORKER_ENABLED=true",
        ]
    )

    return {
        "production_perfection_ready": production_perfection_ready,
        "production_ops_ready": ops_dashboard["production_ops_ready"],
        "maryland_launch_ready": launch_capstone["launch_ready"],
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "production_ops_ready": ops_dashboard["production_ops_ready"],
            "maryland_launch_ready": launch_capstone["launch_ready"],
            "maryland_production_ready": launch_capstone["maryland_production_ready"],
            "twilio_sms_production_ready": launch_capstone["twilio_sms_production_ready"],
            "live_sms_ready": launch_capstone["live_sms_ready"],
            "live_scrapers_all_live": launch_capstone["live_scrapers_all_live"],
            "workers_enabled_count": ops_summary["workers_enabled_count"],
            "workers_running_count": ops_summary["workers_running_count"],
            "launch_urls": launch_capstone["launch_urls"],
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "env_snippet": env_snippet,
        "launch_urls": launch_capstone["launch_urls"],
        "production_ops_dashboard": ops_dashboard,
        "maryland_launch_capstone": launch_capstone,
    }


def run_production_perfection_check(
    db: Session,
    *,
    phone_number: str | None = None,
    probe_scrapers: bool = True,
) -> dict:
    capstone = build_production_perfection_capstone(db)
    launch_smoke = run_maryland_launch_smoke(
        db,
        phone_number=phone_number,
        probe_scrapers=probe_scrapers,
    )
    ops_refresh = refresh_production_ops_dashboard(
        db,
        probe_scrapers=probe_scrapers,
        audit_limit=25,
    )

    launch_smoke_ok = bool(launch_smoke["ok"])
    ops_refresh_ok = bool(ops_refresh["production_ops_ready"])
    static_ready = bool(capstone["production_perfection_ready"])
    ok = static_ready and launch_smoke_ok and ops_refresh_ok

    if ok:
        message = (
            "Production perfection check passed — ops refresh green, launch smoke locked "
            f"{launch_smoke.get('facility_name') or 'demo shift'}"
        )
    elif not static_ready:
        message = "Production perfection check failed — ops dashboard or launch capstone not ready"
    elif not ops_refresh_ok and not launch_smoke_ok:
        message = "Production perfection check failed — ops refresh and launch smoke did not pass"
    elif not ops_refresh_ok:
        message = "Production perfection check failed — ops refresh did not report production_ops_ready"
    else:
        message = launch_smoke.get("message") or "Production perfection check failed — launch smoke did not pass"

    return {
        "ok": ok,
        "production_perfection_ready": static_ready,
        "production_ops_ready": capstone["production_ops_ready"],
        "maryland_launch_ready": capstone["maryland_launch_ready"],
        "launch_smoke_ok": launch_smoke_ok,
        "ops_refresh_ok": ops_refresh_ok,
        "launch_smoke": launch_smoke,
        "ops_refresh_summary": ops_refresh["summary"],
        "scraper_probes": ops_refresh.get("scraper_probes") or launch_smoke.get("scraper_probes") or [],
        "facility_name": launch_smoke.get("facility_name"),
        "placement_id": launch_smoke.get("placement_id"),
        "message": message,
    }


def build_production_perfection_capstone_json(db: Session) -> dict:
    snapshot = build_production_perfection_capstone(db)
    return {
        "filename": PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
        "content": json.dumps(snapshot, indent=2),
    }
