"""Maryland production deploy runbook — go-live readiness after live scraper gateway (step 134)."""

from __future__ import annotations

import json

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

    checks: list[dict] = []

    checks.append(
        {
            "id": "maryland_platform",
            "title": "Maryland platform modules",
            "status": "ready" if maryland_ok else "blocked",
            "detail": "Worker landing, credentialing, crisis scrapers, VMS ingest, and outreach present"
            if maryland_ok
            else "Missing Maryland platform modules",
            "action": None if maryland_ok else "Deploy latest backend build",
        }
    )

    gateway = str(settings.LIVE_SCRAPER_GATEWAY_BASE_URL or "").strip()
    checks.append(
        {
            "id": "scraper_gateway",
            "title": "Live scraper gateway",
            "status": "ready" if gateway else "blocked",
            "detail": f"LIVE_SCRAPER_GATEWAY_BASE_URL={gateway or '(not set)'}",
            "action": None if gateway else "Set LIVE_SCRAPER_GATEWAY_BASE_URL to your adapter service",
        }
    )

    if settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED:
        mock_status = "warning"
        mock_detail = "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=true — disable before public Maryland launch"
        mock_action = "Set LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=false in production .env"
    else:
        mock_status = "ready"
        mock_detail = "Mock adapters disabled — production adapter gateway expected"
        mock_action = None
    checks.append(
        {
            "id": "mock_adapters_off",
            "title": "Production adapter mode",
            "status": mock_status,
            "detail": mock_detail,
            "action": mock_action,
        }
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
        scraper_action = "Flip remaining *_DRY_RUN=false and probe adapters in Admin → Integrations"
    else:
        scraper_status = "blocked"
        scraper_detail = f"All {scraper_summary['total_channels']} scraper channels still in dry-run"
        scraper_action = "Complete step 133 go-live profile and probe all channels"
    checks.append(
        {
            "id": "live_scrapers",
            "title": "Live scraper channels",
            "status": scraper_status,
            "detail": scraper_detail,
            "action": scraper_action,
        }
    )

    staffing_ok = settings.STAFFING_VMS_WORKER_ENABLED and settings.STAFFING_JOB_BOARD_WORKER_ENABLED
    checks.append(
        {
            "id": "staffing_scheduler",
            "title": "Staffing background scheduler",
            "status": "ready" if staffing_ok else "warning",
            "detail": "VMS poll + job board crisis workers enabled"
            if staffing_ok
            else "One or both staffing workers disabled",
            "action": None
            if staffing_ok
            else "Set STAFFING_VMS_WORKER_ENABLED=true and STAFFING_JOB_BOARD_WORKER_ENABLED=true",
        }
    )

    compliance_ok = settings.COMPLIANCE_MONITOR_WORKER_ENABLED
    checks.append(
        {
            "id": "compliance_scheduler",
            "title": "Compliance monitor scheduler",
            "status": "ready" if compliance_ok else "warning",
            "detail": "Hourly document expiration sweeps enabled"
            if compliance_ok
            else "COMPLIANCE_MONITOR_WORKER_ENABLED=false",
            "action": None if compliance_ok else "Set COMPLIANCE_MONITOR_WORKER_ENABLED=true",
        }
    )

    https_ok = public_base.startswith("https://")
    checks.append(
        {
            "id": "public_https",
            "title": "Public HTTPS base URL",
            "status": "ready" if https_ok else "blocked",
            "detail": f"PUBLIC_BASE_URL={public_base or '(not set)'}",
            "action": None if https_ok else "Set PUBLIC_BASE_URL=https://your-domain.com",
        }
    )

    if postgis["postgis_enabled"]:
        postgis_status = "ready"
        postgis_detail = f"PostGIS {postgis['postgis_version']} with GiST-indexed geography columns"
        postgis_action = None
    elif postgis["postgis_version"]:
        postgis_status = "warning"
        postgis_detail = f"PostGIS {postgis['postgis_version']} installed — columns or flag incomplete"
        postgis_action = "Run alembic upgrade head on PostGIS-enabled database"
    else:
        postgis_status = "warning"
        postgis_detail = "PostGIS not detected — geo matching uses Haversine fallback"
        postgis_action = "Use postgis/postgis image and run alembic upgrade head"
    checks.append(
        {
            "id": "postgis_geo",
            "title": "PostGIS geo matching",
            "status": postgis_status,
            "detail": postgis_detail,
            "action": postgis_action,
        }
    )

    blocked = sum(1 for row in checks if row["status"] == "blocked")
    warnings = sum(1 for row in checks if row["status"] == "warning")
    ready = sum(1 for row in checks if row["status"] == "ready")
    production_ready = blocked == 0 and scraper_summary["all_live"] and not settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED

    probes: list[dict] = []
    if include_probes and scraper_summary["all_live"]:
        probes = [row.__dict__ for row in probe_all_live_scrapers()]

    production_env = [
        "# Maryland production launch (OfferCare step 134)",
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
