"""Maryland production launch capstone — Maryland + Twilio + end-to-end smoke (step 136)."""

from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.services.live_scraper_probes import probe_all_live_scrapers
from app.services.maryland_production_runbook import build_maryland_production_runbook
from app.services.twilio_lock_reply_smoke import run_twilio_lock_reply_smoke
from app.services.twilio_sms_production_runbook import build_twilio_sms_production_runbook

MARYLAND_LAUNCH_CAPSTONE_JSON_FILENAME = "offercare-maryland-launch-capstone.json"


def _probe_rows() -> list[dict]:
    return [asdict(row) for row in probe_all_live_scrapers()]


def build_maryland_launch_capstone(db: Session, *, include_probes: bool = False) -> dict:
    md_production = build_maryland_production_runbook(db, include_probes=include_probes)
    sms_production = build_twilio_sms_production_runbook(db)
    md_summary = md_production["summary"]
    sms_summary = sms_production["summary"]

    checks: list[dict] = []

    if md_production["production_ready"]:
        md_status = "ready"
        md_detail = "Maryland production runbook green — live scrapers, schedulers, HTTPS, and production adapter mode"
        md_action = None
    elif md_summary["blocked"] > 0:
        md_status = "blocked"
        md_detail = (
            f"Maryland production blocked — {md_summary['blocked']} blocker(s), "
            f"{md_summary['warnings']} warning(s)"
        )
        md_action = "Admin → Deploy → Maryland production runbook — resolve blockers"
    else:
        md_status = "warning"
        md_detail = (
            f"Maryland production partial — {md_summary['ready']} ready, "
            f"{md_summary['warnings']} warning(s); "
            f"live scrapers {md_summary['live_scrapers_live_count']}/5"
        )
        md_action = "Complete live scraper go-live, disable mock adapters, and set PUBLIC_BASE_URL"
    checks.append(
        {
            "id": "maryland_production",
            "title": "Maryland production readiness",
            "status": md_status,
            "detail": md_detail,
            "action": md_action,
        }
    )

    if sms_production["production_ready"]:
        sms_status = "ready"
        sms_detail = "Twilio live SMS production ready — outbound, inbound webhook, and signatures configured"
        sms_action = None
    elif sms_summary["blocked"] > 0:
        sms_status = "blocked"
        sms_detail = (
            f"Live SMS blocked — {sms_summary['blocked']} blocker(s), {sms_summary['warnings']} warning(s)"
        )
        sms_action = "Admin → Integrations → Copy Twilio go-live .env and wire Twilio Console webhook"
    else:
        sms_status = "warning"
        sms_detail = (
            f"Live SMS partial — {sms_summary['ready']} ready, {sms_summary['warnings']} warning(s)"
        )
        sms_action = "Set SMS_DRY_RUN=false, PUBLIC_BASE_URL, and TWILIO_VALIDATE_SIGNATURES=true"
    checks.append(
        {
            "id": "live_sms_production",
            "title": "Live SMS production",
            "status": sms_status,
            "detail": sms_detail,
            "action": sms_action,
        }
    )

    launch_ready = md_production["production_ready"] and sms_production["production_ready"]
    if launch_ready:
        launch_status = "ready"
        launch_detail = "Maryland launch capstone green — production scrapers and live SMS both ready for go-live"
        launch_action = None
    elif md_status == "blocked" or sms_status == "blocked":
        launch_status = "blocked"
        launch_detail = "Maryland launch blocked — resolve Maryland production and live SMS blockers first"
        launch_action = "Admin → Deploy → Run launch smoke after both runbooks are green"
    else:
        launch_status = "warning"
        launch_detail = "Maryland launch partial — complete Maryland production and live SMS runbooks"
        launch_action = "Admin → Deploy → Maryland launch capstone — finish remaining warnings"
    checks.append(
        {
            "id": "maryland_launch_capstone",
            "title": "Maryland launch capstone",
            "status": launch_status,
            "detail": launch_detail,
            "action": launch_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")

    steps = [
        "Confirm Maryland production runbook is green — live scraper gateway, all five channels live, schedulers on",
        "Confirm live SMS production runbook is green — SMS_DRY_RUN=false, HTTPS PUBLIC_BASE_URL, Twilio webhook wired",
        "Admin → Integrations → Probe live scrapers — all five channels should return LIVE_OK",
        "Admin → Integrations → Test SMS to verify outbound delivery",
        "Admin → Deploy → Run launch smoke — probes scrapers, notify-matched lock path, and YES reply lock",
        "Share worker landing /join and verify a Maryland CNA/LPN application screens through live MBON/OIG/judiciary",
        "Ops panel → Run VMS poll, job board, compliance, and cascade ticks to warm production schedulers",
        "Notify matched on a broadcasting shift, then text YES from the clinician handset to confirm end-to-end lock",
        "Deploy checklist maryland_launch_capstone should flip to READY when both production runbooks are green",
        "Export Maryland launch capstone JSON for launch sign-off and attach to deploy bundle",
    ]

    env_snippet = "\n".join(
        [
            md_production["env_snippet"],
            "",
            sms_production["env_snippet"],
        ]
    )

    probes = md_production.get("probes") or []

    return {
        "launch_ready": launch_ready,
        "maryland_production_ready": md_production["production_ready"],
        "twilio_sms_production_ready": sms_production["production_ready"],
        "live_sms_ready": sms_production["live_sms_ready"],
        "live_scrapers_all_live": md_summary["live_scrapers_all_live"],
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "maryland_production_ready": md_production["production_ready"],
            "twilio_sms_production_ready": sms_production["production_ready"],
            "live_sms_ready": sms_production["live_sms_ready"],
            "live_scrapers_all_live": md_summary["live_scrapers_all_live"],
            "live_scrapers_live_count": md_summary["live_scrapers_live_count"],
            "inbound_webhook_url": sms_summary.get("inbound_webhook_url"),
            "launch_urls": md_production["launch_urls"],
        },
        "checks": checks,
        "steps": steps,
        "env_snippet": env_snippet,
        "launch_urls": md_production["launch_urls"],
        "probes": probes,
        "maryland_production_runbook": md_production,
        "twilio_sms_production_runbook": sms_production,
    }


def run_maryland_launch_smoke(
    db: Session,
    *,
    phone_number: str | None = None,
    probe_scrapers: bool = True,
) -> dict:
    capstone = build_maryland_launch_capstone(db)
    scraper_probes: list[dict] = []
    scraper_probes_ok = True

    if probe_scrapers:
        if capstone["live_scrapers_all_live"]:
            scraper_probes = _probe_rows()
            scraper_probes_ok = bool(scraper_probes) and all(
                row["status"] == "LIVE_OK" for row in scraper_probes
            )
        else:
            scraper_probes_ok = False

    lock_smoke = run_twilio_lock_reply_smoke(db, phone_number=phone_number)
    lock_ok = bool(lock_smoke["ok"])
    ok = lock_ok and scraper_probes_ok

    if ok:
        message = (
            f"Maryland launch smoke passed — {len(scraper_probes)} scraper probe(s) LIVE_OK "
            f"and {lock_smoke['facility_name']} locked via {lock_smoke['reply_keyword']} reply"
        )
    elif not scraper_probes_ok and not lock_ok:
        message = "Maryland launch smoke failed — scraper probes and lock reply smoke did not pass"
    elif not scraper_probes_ok:
        message = "Maryland launch smoke failed — scraper probes did not all return LIVE_OK"
    else:
        message = lock_smoke.get("message") or "Maryland launch smoke failed — lock reply did not lock shift"

    return {
        "ok": ok,
        "launch_ready": capstone["launch_ready"],
        "scraper_probes_ok": scraper_probes_ok,
        "lock_reply_smoke_ok": lock_ok,
        "scraper_probes": scraper_probes,
        "lock_reply_smoke": lock_smoke,
        "facility_name": lock_smoke.get("facility_name"),
        "placement_id": lock_smoke.get("placement_id"),
        "message": message,
    }


def build_maryland_launch_capstone_json(db: Session, *, include_probes: bool = False) -> dict:
    snapshot = build_maryland_launch_capstone(db, include_probes=include_probes)
    return {
        "filename": MARYLAND_LAUNCH_CAPSTONE_JSON_FILENAME,
        "content": json.dumps(snapshot, indent=2),
    }
