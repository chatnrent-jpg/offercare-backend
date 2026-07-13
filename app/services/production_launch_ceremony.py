"""Production launch ceremony — stakeholder sign-off + deploy bundle export (step 139)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.deploy_walkthrough import DEPLOY_EXPORT_ZIP_FILENAME
from app.services.production_perfection_capstone import (
    PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
    build_production_perfection_capstone,
    run_production_perfection_check,
)

PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME = "offercare-production-launch-ceremony.json"
PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME = "offercare-production-launch-ceremony.md"

_CEREMONY_ARTIFACTS = (
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
    "README.txt",
)


def _status_label(ready: bool) -> str:
    return "READY" if ready else "NOT YET"


def _build_signoff_markdown(ceremony: dict) -> str:
    summary = ceremony["summary"]
    perfection = ceremony["production_perfection_capstone"]
    perfection_summary = perfection["summary"]
    launch_urls = ceremony["launch_urls"]
    lines = [
        "# VettedMe Maryland Production Launch Ceremony",
        "",
        f"Generated: {summary.get('refreshed_at', datetime.now(timezone.utc).isoformat())}",
        "",
        "## Executive summary",
        "",
        f"- **Launch ceremony:** {_status_label(ceremony['launch_ceremony_ready'])}",
        f"- **Production perfection:** {_status_label(perfection['production_perfection_ready'])}",
        f"- **Production ops:** {_status_label(perfection['production_ops_ready'])}",
        f"- **Maryland launch:** {_status_label(perfection['maryland_launch_ready'])}",
        f"- **Live scrapers all live:** {_status_label(summary.get('live_scrapers_all_live', False))}",
        f"- **Deploy bundle:** {DEPLOY_EXPORT_ZIP_FILENAME} ({summary.get('deploy_bundle_file_count', 15)} files)",
        "",
        "## Launch URLs",
        "",
        f"- Worker landing: {launch_urls.get('join', '/join')}",
        f"- Admin: {launch_urls.get('admin', '/admin')}",
        f"- Health: {launch_urls.get('health', '/health')}",
        f"- Clinician portal: {launch_urls.get('portal', '/portal')}",
        "",
        "## Ceremony checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for row in ceremony["checks"]:
        lines.append(f"| {row['title']} | {row['status'].upper()} | {row['detail']} |")
    lines.extend(
        [
            "",
            "## Production perfection capstone",
            "",
            f"- Checks ready: {perfection_summary.get('ready', '—')}",
            f"- Warnings: {perfection_summary.get('warnings', '—')}",
            f"- Blocked: {perfection_summary.get('blocked', '—')}",
            f"- Workers enabled: {perfection_summary.get('workers_enabled_count', '—')}/4",
            "",
            "## Deploy bundle artifacts",
            "",
        ]
    )
    for artifact in ceremony.get("bundle_artifacts") or _CEREMONY_ARTIFACTS:
        lines.append(f"- {artifact}")
    lines.extend(
        [
            "",
            "## Stakeholder sign-off",
            "",
            "- [ ] Engineering lead — production perfection check passed",
            "- [ ] Operations lead — production ops dashboard green",
            "- [ ] Clinical operations — Maryland launch capstone green",
            "- [ ] Compliance — live scrapers and COMAR monitors verified",
            "- [ ] Executive sponsor — deploy bundle archived for launch record",
            "",
            "## Ceremony steps completed",
            "",
        ]
    )
    for index, step in enumerate(ceremony.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")
    lines.append("")
    return "\n".join(lines)


def build_production_launch_ceremony(db: Session) -> dict:
    perfection = build_production_perfection_capstone(db)
    perfection_summary = perfection["summary"]
    bundle_file_count = len(_CEREMONY_ARTIFACTS)

    checks: list[dict] = []

    if perfection["production_perfection_ready"]:
        perf_status = "ready"
        perf_detail = "Production perfection green — ready for launch ceremony sign-off"
        perf_action = None
    elif perfection_summary["blocked"] > 0:
        perf_status = "blocked"
        perf_detail = (
            f"Production perfection blocked — {perfection_summary['blocked']} blocker(s)"
        )
        perf_action = "Admin → Production perfection → Run production perfection check"
    else:
        perf_status = "warning"
        perf_detail = "Production perfection partial — complete ops and launch capstones first"
        perf_action = "Admin → Production perfection → Run production perfection check"
    checks.append(
        {
            "id": "production_perfection",
            "title": "Production perfection",
            "status": perf_status,
            "detail": perf_detail,
            "action": perf_action,
        }
    )

    bundle_status = "ready"
    bundle_detail = (
        f"Deploy bundle available — {bundle_file_count} files in {DEPLOY_EXPORT_ZIP_FILENAME}"
    )
    checks.append(
        {
            "id": "deploy_bundle",
            "title": "Deploy bundle export",
            "status": bundle_status,
            "detail": bundle_detail,
            "action": None,
        }
    )

    launch_ceremony_ready = perfection["production_perfection_ready"]
    if launch_ceremony_ready:
        ceremony_status = "ready"
        ceremony_detail = "Launch ceremony green — perfection, bundle, and sign-off document ready"
        ceremony_action = None
    elif perf_status == "blocked":
        ceremony_status = "blocked"
        ceremony_detail = "Launch ceremony blocked — production perfection must be green first"
        ceremony_action = "Admin → Production launch ceremony → Run launch ceremony after perfection is green"
    else:
        ceremony_status = "warning"
        ceremony_detail = "Launch ceremony partial — run perfection check before stakeholder sign-off"
        ceremony_action = "Admin → Production launch ceremony → Run launch ceremony"
    checks.append(
        {
            "id": "production_launch_ceremony",
            "title": "Production launch ceremony",
            "status": ceremony_status,
            "detail": ceremony_detail,
            "action": ceremony_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    steps = [
        "Confirm production_perfection_ready is true on /health and Admin perfection panel",
        "Admin → Production launch ceremony → Run launch ceremony — perfection check + sign-off snapshot",
        "Download production launch ceremony sign-off (.md) for stakeholder review",
        "Download deploy bundle (.zip) — full 14-file production archive including ceremony artifacts",
        "Export production launch ceremony JSON for structured launch record",
        "Complete stakeholder sign-off checklist in the ceremony markdown",
        "Share worker landing /join URL with Maryland operations for go-live communications",
        "Archive deploy bundle and ceremony markdown for compliance and launch audit trail",
    ]

    ceremony = {
        "launch_ceremony_ready": launch_ceremony_ready,
        "production_perfection_ready": perfection["production_perfection_ready"],
        "production_ops_ready": perfection["production_ops_ready"],
        "maryland_launch_ready": perfection["maryland_launch_ready"],
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "production_perfection_ready": perfection["production_perfection_ready"],
            "production_ops_ready": perfection["production_ops_ready"],
            "maryland_launch_ready": perfection["maryland_launch_ready"],
            "live_scrapers_all_live": perfection_summary.get("live_scrapers_all_live"),
            "deploy_bundle_file_count": bundle_file_count,
            "deploy_bundle_filename": DEPLOY_EXPORT_ZIP_FILENAME,
            "perfection_capstone_filename": PRODUCTION_PERFECTION_CAPSTONE_JSON_FILENAME,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "checks": checks,
        "steps": steps,
        "launch_urls": perfection["launch_urls"],
        "bundle_artifacts": list(_CEREMONY_ARTIFACTS),
        "production_perfection_capstone": perfection,
    }
    ceremony["signoff_markdown"] = _build_signoff_markdown(ceremony)
    return ceremony


def build_production_launch_ceremony_markdown(db: Session) -> dict:
    ceremony = build_production_launch_ceremony(db)
    return {
        "filename": PRODUCTION_LAUNCH_CEREMONY_MD_FILENAME,
        "markdown": ceremony["signoff_markdown"],
    }


def build_production_launch_ceremony_json(db: Session) -> dict:
    ceremony = build_production_launch_ceremony(db)
    return {
        "filename": PRODUCTION_LAUNCH_CEREMONY_JSON_FILENAME,
        "content": json.dumps(ceremony, indent=2),
    }


def run_production_launch_ceremony(
    db: Session,
    *,
    phone_number: str | None = None,
    probe_scrapers: bool = True,
) -> dict:
    perfection_check = run_production_perfection_check(
        db,
        phone_number=phone_number,
        probe_scrapers=probe_scrapers,
    )
    ceremony = build_production_launch_ceremony(db)
    ok = bool(perfection_check["ok"]) and bool(ceremony["launch_ceremony_ready"])

    if ok:
        message = (
            "Production launch ceremony passed — perfection check OK and stakeholder sign-off "
            f"document ready ({ceremony['summary']['deploy_bundle_file_count']} deploy bundle files)"
        )
    elif not ceremony["launch_ceremony_ready"]:
        message = "Production launch ceremony failed — production perfection is not green"
    elif not perfection_check["ok"]:
        message = perfection_check.get("message") or "Production launch ceremony failed — perfection check did not pass"
    else:
        message = "Production launch ceremony failed"

    return {
        "ok": ok,
        "launch_ceremony_ready": ceremony["launch_ceremony_ready"],
        "production_perfection_ready": ceremony["production_perfection_ready"],
        "perfection_check_ok": bool(perfection_check["ok"]),
        "perfection_check": perfection_check,
        "signoff_markdown": ceremony["signoff_markdown"],
        "deploy_bundle_filename": ceremony["summary"]["deploy_bundle_filename"],
        "deploy_bundle_file_count": ceremony["summary"]["deploy_bundle_file_count"],
        "facility_name": perfection_check.get("facility_name"),
        "placement_id": perfection_check.get("placement_id"),
        "message": message,
    }
