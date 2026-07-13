"""Maryland production deploy runbook — go-live readiness after live scraper gateway (step 134)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.services.deploy_walkthrough import _maryland_platform_present
from app.services.live_scraper_go_live import build_live_scraper_go_live_profile
from app.services.live_scraper_probes import probe_all_live_scrapers
from app.services.live_scrapers import live_scrapers_summary
from app.services.postgis_geo import describe_postgis_status

MARYLAND_PRODUCTION_RUNBOOK_JSON_FILENAME = "offercare-maryland-production-runbook.json"


def _public_base() -> str:
    return str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")


def build_maryland_production_runbook(db: Session, *, include_probes: bool = False) -> dict:
    public_base = _public_base()
    scraper_summary = live_scrapers_summary()
    go_live = build_live_scraper_go_live_profile()
    postgis = describe_postgis_status(db)
    maryland_ok = _maryland_platform_present()
    checked_at = datetime.now(timezone.utc).isoformat()

    checks: list[dict] = []

    checks.append(
        {
            "id": "maryland_platform",
            "name": "Maryland Platform Modules",
            "layer": "OHCQ / Infrastructure",
            "status": "PASSED" if maryland_ok else "BLOCKED",
            "checked_at": checked_at,
            "passed": maryland_ok,
        }
    )

    gateway = str(settings.LIVE_SCRAPER_GATEWAY_BASE_URL or "").strip()
    checks.append(
        {
            "id": "scraper_gateway",
            "name": "Live Scraper Gateway",
            "layer": "OHCQ / MBON Validation",
            "status": "PASSED" if gateway else "BLOCKED",
            "checked_at": checked_at,
            "passed": bool(gateway),
        }
    )

    mock_adapters_ok = not settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED
    checks.append(
        {
            "id": "mock_adapters_off",
            "name": "Production Adapter Mode",
            "layer": "OHCQ / Infrastructure",
            "status": "PASSED" if mock_adapters_ok else "WARNING",
            "checked_at": checked_at,
            "passed": mock_adapters_ok,
        }
    )

    if scraper_summary["all_live"]:
        scraper_status = "PASSED"
    elif scraper_summary["live_ready_count"] > 0:
        scraper_status = "WARNING"
    else:
        scraper_status = "BLOCKED"
    
    checks.append(
        {
            "id": "live_scrapers",
            "name": "MBON/OIG/Judiciary Live Scrapers",
            "layer": "OHCQ / MBON Validation",
            "status": scraper_status,
            "checked_at": checked_at,
            "passed": scraper_summary["all_live"],
        }
    )

    staffing_ok = settings.STAFFING_VMS_WORKER_ENABLED and settings.STAFFING_JOB_BOARD_WORKER_ENABLED
    checks.append(
        {
            "id": "staffing_scheduler",
            "name": "Staffing Background Scheduler",
            "layer": "OHCQ / Infrastructure",
            "status": "PASSED" if staffing_ok else "WARNING",
            "checked_at": checked_at,
            "passed": staffing_ok,
        }
    )

    compliance_ok = settings.COMPLIANCE_MONITOR_WORKER_ENABLED
    checks.append(
        {
            "id": "compliance_scheduler",
            "name": "Compliance Monitor Scheduler",
            "layer": "OHCQ / Compliance",
            "status": "PASSED" if compliance_ok else "WARNING",
            "checked_at": checked_at,
            "passed": compliance_ok,
        }
    )

    https_ok = public_base.startswith("https://")
    checks.append(
        {
            "id": "public_https",
            "name": "Public HTTPS Base URL",
            "layer": "OHCQ / Infrastructure",
            "status": "PASSED" if https_ok else "BLOCKED",
            "checked_at": checked_at,
            "passed": https_ok,
        }
    )

    if postgis["postgis_enabled"]:
        postgis_status = "PASSED"
        postgis_passed = True
    elif postgis["postgis_version"]:
        postgis_status = "WARNING"
        postgis_passed = False
    else:
        postgis_status = "WARNING"
        postgis_passed = False
    
    checks.append(
        {
            "id": "postgis_geo",
            "name": "PostGIS Geo Matching",
            "layer": "OHCQ / Infrastructure",
            "status": postgis_status,
            "checked_at": checked_at,
            "passed": postgis_passed,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "BLOCKED")
    warnings = sum(1 for row in checks if row["status"] == "WARNING")
    ready = sum(1 for row in checks if row["status"] == "PASSED")
    production_ready = blocked == 0 and scraper_summary["all_live"] and not settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED

    probes: list[dict] = []
    if include_probes and scraper_summary["all_live"]:
        probes = [row.__dict__ for row in probe_all_live_scrapers()]

    production_env = [
        "# Maryland production launch (VettedCare step 134)",
        f"LIVE_SCRAPER_GATEWAY_BASE_URL={gateway or 'https://adapters.yourdomain.com'}",
        "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=false",
        "MBON_VERIFY_DRY_RUN=false",
        "OIG_SCREEN_DRY_RUN=false",
        "MD_JUDICIARY_DRY_RUN=false",
        "JOB_BOARD_SCRAPE_DRY_RUN=false",
        "VMS_INGEST_DRY_RUN=false",
        "STAFFING_VMS_WORKER_ENABLED=true",
        "STAFFING_JOB_BOARD_WORKER_ENABLED=true",
        "COMPLIANCE_MONITOR_WORKER_ENABLED=true",
        f"PUBLIC_BASE_URL={public_base or 'https://api.yourdomain.com'}",
    ]

    steps = [
        "docker compose up -d --build on a PostGIS-enabled PostgreSQL host",
        "alembic upgrade head — confirm deploy checklist migrations item is ready",
        "Set LIVE_SCRAPER_GATEWAY_BASE_URL to production adapters and LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=false",
        "Flip MBON, OIG, judiciary, job board, and VMS ingest *_DRY_RUN=false",
        "Admin → Integrations → Probe live scrapers — all five channels should return LIVE_OK",
        "Admin → Ops → Run VMS poll, job board, and compliance ticks to warm caches",
        "Share worker landing /join for Maryland CNA/LPN/GNA applications",
        "Admin → Maryland COMAR compliance — confirm live MBON/OIG/judiciary screens on a test applicant",
        "Set PUBLIC_BASE_URL and wire Twilio inbound webhook for live SMS lock replies",
        "Admin → Integrations → Run Twilio lock reply smoke after live SMS go-live",
        "Deploy walkthrough panel renders Maryland production runbook after refresh",
        "Shift Sniper dispatches matched clinicians within 5 minutes of VMS ingest or manual offer broadcast",
    ]

    launch_urls = {
        "join": f"{public_base}/join" if public_base else "/join",
        "admin": f"{public_base}/admin" if public_base else "/admin",
        "health": f"{public_base}/health" if public_base else "/health",
        "portal": f"{public_base}/portal" if public_base else "/portal",
    }

    return {
        "production_ready": production_ready,
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "live_scrapers_all_live": scraper_summary["all_live"],
            "live_scrapers_live_count": scraper_summary["live_ready_count"],
            "mock_adapters_enabled": settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED,
            "gateway_base_url": gateway or None,
        },
        "checks": checks,
        "steps": steps,
        "go_live_profile": go_live,
        "probes": probes,
        "env_snippet": "\n".join(production_env),
        "launch_urls": launch_urls,
    }


def build_maryland_production_runbook_json(db: Session, *, include_probes: bool = False) -> dict:
    snapshot = build_maryland_production_runbook(db, include_probes=include_probes)
    return {
        "filename": MARYLAND_PRODUCTION_RUNBOOK_JSON_FILENAME,
        "content": json.dumps(snapshot, indent=2),
    }
