"""Production deploy checklist — Docker, migrations, and live Twilio webhook."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.migrations import ROOT, _alembic_config
from app.services.integrations import twilio_inbound_webhook_url
from app.services.postgis_geo import describe_postgis_status
from app.services.live_scrapers import live_scrapers_summary
from app.services.demo_environment import (
    DEMO_ADMIN_ACTION_DEMO_GATES,
    append_demo_admin_actions_csv,
    build_demo_active_gates,
    build_demo_environment_status,
    demo_walkthrough_intact,
    build_demo_gates_json,
    build_demo_gates_summary,
    build_demo_gates_txt,
    build_demo_status_csv,
    build_demo_status_json,
    build_demo_walkthrough_script,
    DEMO_GATES_JSON_FILENAME,
    DEMO_GATES_TXT_FILENAME,
)
from app.services.states import supported_states

DEFAULT_ADMIN_KEY = "change-me-to-a-long-random-string"
DEFAULT_JWT_SECRET = "offercare-dev-secret-change-in-production"
DEPLOY_CHECKLIST_JSON_FILENAME = "offercare-deploy-checklist.json"
DEPLOY_CHECKLIST_CSV_FILENAME = "offercare-deploy-checklist.csv"
DEPLOY_EXPORT_ZIP_FILENAME = "offercare-deploy-bundle.zip"
DEPLOY_EXPORT_README_FILENAME = "README.txt"


@dataclass(frozen=True)
class DeployCheckItem:
    id: str
    title: str
    status: str
    detail: str
    action: str | None = None


def _deploy_artifacts_present() -> bool:
    return all(
        (ROOT / name).exists()
        for name in ("Dockerfile", "docker-compose.yml", "scripts/docker-entrypoint.sh", "alembic.ini")
    )


def _portal_pwa_present() -> bool:
    portal_dir = ROOT / "app" / "static" / "portal"
    return all((portal_dir / name).exists() for name in ("manifest.webmanifest", "sw.js", "index.html"))


def _maryland_platform_present() -> bool:
    landing_dir = ROOT / "app" / "static" / "landing"
    services = ROOT / "app" / "services"
    required = (
        landing_dir / "index.html",
        landing_dir / "app.js",
        services / "maryland_landing.py",
        services / "compliance_monitor.py",
        services / "credentialing_pipeline.py",
        services / "job_board_crisis_scraper.py",
        services / "vms_shift_ingestion.py",
        services / "outreach_pipeline.py",
    )
    return all(path.exists() for path in required)


def _migrations_at_head(engine: Engine) -> tuple[bool, str]:
    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        return False, "alembic_version table missing — run migrations"
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current = context.get_current_revision()
    if current == head:
        return True, f"At head ({head})"
    return False, f"Revision {current or 'none'} — upgrade to {head}"


def build_deploy_checklist(
    db: Session,
    *,
    include_launch_archive: bool = True,
    include_launch_finale: bool = True,
    include_launch_bundle_verification: bool = True,
) -> dict:
    engine = db.get_bind()
    items: list[DeployCheckItem] = []

    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "PostgreSQL connection OK"
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        db_detail = f"Database error: {exc}"

    items.append(
        DeployCheckItem(
            id="database",
            title="PostgreSQL",
            status="ready" if db_ok else "blocked",
            detail=db_detail,
            action=None if db_ok else "Start PostgreSQL or run docker compose up db",
        )
    )

    artifacts_ok = _deploy_artifacts_present()
    items.append(
        DeployCheckItem(
            id="docker",
            title="Docker artifacts",
            status="ready" if artifacts_ok else "blocked",
            detail="Dockerfile, compose, entrypoint, and Alembic config present"
            if artifacts_ok
            else "Missing deploy files in repository root",
            action=None if artifacts_ok else "Pull latest repo — deploy files should ship with the API",
        )
    )

    if db_ok:
        mig_ok, mig_detail = _migrations_at_head(engine)
        items.append(
            DeployCheckItem(
                id="migrations",
                title="Alembic migrations",
                status="ready" if mig_ok else "blocked",
                detail=mig_detail,
                action=None if mig_ok else "Run: alembic upgrade head (or restart API container)",
            )
        )
    else:
        items.append(
            DeployCheckItem(
                id="migrations",
                title="Alembic migrations",
                status="pending",
                detail="Connect database first",
                action="Fix DATABASE_URL then run alembic upgrade head",
            )
        )

    admin_key = str(settings.ADMIN_API_KEY or "").strip()
    admin_ok = bool(admin_key) and admin_key != DEFAULT_ADMIN_KEY
    items.append(
        DeployCheckItem(
            id="admin_key",
            title="Admin API key",
            status="ready" if admin_ok else "warning",
            detail="Custom ADMIN_API_KEY configured" if admin_ok else "Set a strong ADMIN_API_KEY before exposing /admin",
            action=None if admin_ok else "Generate a long random string in .env",
        )
    )

    jwt_ok = settings.JWT_SECRET_KEY != DEFAULT_JWT_SECRET
    items.append(
        DeployCheckItem(
            id="jwt_secret",
            title="Clinician JWT secret",
            status="ready" if jwt_ok else "warning",
            detail="JWT_SECRET_KEY customized" if jwt_ok else "Using dev JWT secret — rotate before production",
            action=None if jwt_ok else "Set JWT_SECRET_KEY in .env",
        )
    )

    twilio_cfg = settings.twilio_configured
    items.append(
        DeployCheckItem(
            id="twilio_credentials",
            title="Twilio credentials",
            status="ready" if twilio_cfg else "pending",
            detail="Account SID, auth token, and from number set"
            if twilio_cfg
            else "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER",
            action=None if twilio_cfg else "Copy values from Twilio Console → Account",
        )
    )

    live_sms = twilio_cfg and not settings.SMS_DRY_RUN
    items.append(
        DeployCheckItem(
            id="twilio_live",
            title="Live SMS mode",
            status="ready" if live_sms else "pending",
            detail="SMS_DRY_RUN=false — outbound SMS enabled"
            if live_sms
            else "SMS still in dry-run (safe for local dev)",
            action=None if live_sms else "Set SMS_DRY_RUN=false when ready to send real texts",
        )
    )

    public_base = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    public_ok = public_base.startswith("https://")
    webhook_url = twilio_inbound_webhook_url()
    items.append(
        DeployCheckItem(
            id="public_url",
            title="Public HTTPS base URL",
            status="ready" if public_ok else "blocked" if live_sms else "pending",
            detail=f"PUBLIC_BASE_URL={public_base or '(not set)'}"
            + (f" → webhook {webhook_url}" if webhook_url else ""),
            action="Set PUBLIC_BASE_URL=https://your-domain.com (no trailing slash)"
            if not public_ok
            else None,
        )
    )

    sig_ok = settings.TWILIO_VALIDATE_SIGNATURES
    items.append(
        DeployCheckItem(
            id="twilio_signatures",
            title="Twilio signature validation",
            status="ready" if sig_ok else "warning" if live_sms else "pending",
            detail="TWILIO_VALIDATE_SIGNATURES=true — inbound webhook verified"
            if sig_ok
            else "Signature check off — enable before public Twilio webhook",
            action=None if sig_ok else "Set TWILIO_VALIDATE_SIGNATURES=true in production",
        )
    )

    if webhook_url and live_sms:
        twilio_webhook_status = "ready" if public_ok else "blocked"
        twilio_webhook_detail = (
            f"Paste this URL in Twilio Console → Phone Numbers → "
            f"Messaging → A MESSAGE COMES IN → Webhook: {webhook_url}"
        )
    elif webhook_url:
        twilio_webhook_status = "pending"
        twilio_webhook_detail = f"When live, configure Twilio inbound webhook: {webhook_url}"
    else:
        twilio_webhook_status = "pending"
        twilio_webhook_detail = "Set PUBLIC_BASE_URL to generate inbound webhook URL"

    items.append(
        DeployCheckItem(
            id="twilio_webhook",
            title="Twilio inbound webhook",
            status=twilio_webhook_status,
            detail=twilio_webhook_detail,
            action="Twilio Console → your number → Messaging → Webhook URL (POST)"
            if twilio_webhook_status != "ready"
            else None,
        )
    )

    email_cfg = settings.email_configured
    items.append(
        DeployCheckItem(
            id="email_smtp",
            title="Email shift alerts",
            status="ready" if email_cfg and not settings.EMAIL_DRY_RUN else "pending",
            detail="SMTP configured and EMAIL_DRY_RUN=false"
            if email_cfg and not settings.EMAIL_DRY_RUN
            else "SMTP host/from set — still dry-run"
            if email_cfg
            else "Set SMTP_HOST and EMAIL_FROM for email alerts",
            action=None
            if email_cfg and not settings.EMAIL_DRY_RUN
            else "Set SMTP credentials and EMAIL_DRY_RUN=false when ready",
        )
    )

    push_cfg = settings.push_configured
    items.append(
        DeployCheckItem(
            id="push_vapid",
            title="Web Push alerts",
            status="ready" if push_cfg and not settings.PUSH_DRY_RUN else "pending",
            detail="VAPID keys configured and PUSH_DRY_RUN=false"
            if push_cfg and not settings.PUSH_DRY_RUN
            else "VAPID keys set — still dry-run"
            if push_cfg
            else "Generate VAPID keys and set VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY",
            action=None
            if push_cfg and not settings.PUSH_DRY_RUN
            else "Portal clinicians enable push at /portal after keys are live",
        )
    )

    portal_ok = _portal_pwa_present()
    items.append(
        DeployCheckItem(
            id="portal_pwa",
            title="Clinician portal PWA",
            status="ready" if portal_ok else "blocked",
            detail="Portal manifest, service worker, and shell present"
            if portal_ok
            else "Missing /portal static assets",
            action=None if portal_ok else "Deploy latest build — portal ships under app/static/portal",
        )
    )

    maryland_ok = _maryland_platform_present()
    items.append(
        DeployCheckItem(
            id="maryland_platform",
            title="Maryland staffing platform",
            status="ready" if maryland_ok else "blocked",
            detail="Worker landing (/join), credentialing, crisis scrapers, VMS ingest, and outreach pipeline present"
            if maryland_ok
            else "Missing Maryland platform modules — deploy latest backend build",
            action=None if maryland_ok else "Pull latest code and verify migrations through 011_postgis_geo",
        )
    )

    if db_ok:
        postgis = describe_postgis_status(db)
        postgis_ready = postgis["postgis_enabled"]
        if postgis["postgis_version"] and not postgis_ready:
            postgis_status = "warning"
            postgis_detail = (
                f"PostGIS {postgis['postgis_version']} installed — "
                f"columns={'ready' if postgis['postgis_columns_ready'] else 'missing'}; "
                f"GEO_MATCH_USE_POSTGIS={postgis['geo_match_use_postgis']}"
            )
            postgis_action = "Run alembic upgrade head on a PostGIS-enabled database (docker compose db image)"
        elif postgis_ready:
            postgis_status = "ready"
            postgis_detail = f"PostGIS {postgis['postgis_version']} with GiST-indexed geography columns"
            postgis_action = None
        else:
            postgis_status = "warning"
            postgis_detail = "PostGIS extension not detected — geo matching uses Haversine fallback"
            postgis_action = "Use postgis/postgis image in docker-compose and run alembic upgrade head"
        items.append(
            DeployCheckItem(
                id="postgis_geo",
                title="PostGIS geo matching",
                status=postgis_status,
                detail=postgis_detail,
                action=postgis_action,
            )
        )

    staffing_vms = settings.STAFFING_VMS_WORKER_ENABLED
    staffing_board = settings.STAFFING_JOB_BOARD_WORKER_ENABLED
    if staffing_vms or staffing_board:
        parts = []
        if staffing_vms:
            parts.append(f"VMS poll every {settings.STAFFING_VMS_WORKER_INTERVAL_SECONDS // 60}m")
        if staffing_board:
            parts.append(
                f"job board scan every {settings.STAFFING_JOB_BOARD_WORKER_INTERVAL_SECONDS // 3600}h"
            )
        items.append(
            DeployCheckItem(
                id="staffing_scheduler",
                title="Staffing background scheduler",
                status="ready",
                detail="; ".join(parts),
                action=None,
            )
        )
    else:
        items.append(
            DeployCheckItem(
                id="staffing_scheduler",
                title="Staffing background scheduler",
                status="warning",
                detail="VMS and job board workers disabled in config",
                action="Set STAFFING_VMS_WORKER_ENABLED=true and STAFFING_JOB_BOARD_WORKER_ENABLED=true",
            )
        )

    if settings.COMPLIANCE_MONITOR_WORKER_ENABLED:
        items.append(
            DeployCheckItem(
                id="compliance_scheduler",
                title="Compliance monitor scheduler",
                status="ready",
                detail=(
                    f"Document expiration sweep every "
                    f"{settings.COMPLIANCE_MONITOR_WORKER_INTERVAL_SECONDS // 3600}h"
                ),
                action=None,
            )
        )
    else:
        items.append(
            DeployCheckItem(
                id="compliance_scheduler",
                title="Compliance monitor scheduler",
                status="warning",
                detail="COMPLIANCE_MONITOR_WORKER_ENABLED=false — no automatic expiration sweeps",
                action="Set COMPLIANCE_MONITOR_WORKER_ENABLED=true",
            )
        )

    scraper_summary = live_scrapers_summary()
    if scraper_summary["all_live"]:
        scraper_status = "ready"
        scraper_detail = "All credentialing and ingest scrapers are live-ready"
        scraper_action = None
    elif scraper_summary["live_ready_count"] > 0:
        scraper_status = "warning"
        scraper_detail = (
            f"{scraper_summary['live_ready_count']}/{scraper_summary['total_channels']} "
            f"scraper channels live · {scraper_summary['dry_run_count']} still dry-run"
        )
        scraper_action = "Configure LIVE_SCRAPER_GATEWAY_BASE_URL, flip *_DRY_RUN=false, and probe adapters in Admin → Integrations"
    else:
        scraper_status = "pending"
        scraper_detail = (
            f"All {scraper_summary['total_channels']} scraper channels in dry-run — "
            "MBON, OIG, judiciary, job board, VMS ingest"
        )
        scraper_action = "Configure LIVE_SCRAPER_GATEWAY_BASE_URL and set *_DRY_RUN=false when ready for production"
    items.append(
        DeployCheckItem(
            id="live_scrapers",
            title="Live scraper readiness",
            status=scraper_status,
            detail=scraper_detail,
            action=scraper_action,
        )
    )

    from app.services.maryland_production_runbook import build_maryland_production_runbook

    md_production = build_maryland_production_runbook(db)
    md_prod_summary = md_production["summary"]
    if md_production["production_ready"]:
        md_prod_status = "ready"
        md_prod_detail = "Maryland production runbook green — live scrapers, schedulers, HTTPS, and production adapter mode"
        md_prod_action = None
    elif md_prod_summary["blocked"] > 0:
        md_prod_status = "blocked"
        md_prod_detail = (
            f"Maryland production blocked — {md_prod_summary['blocked']} blocker(s), "
            f"{md_prod_summary['warnings']} warning(s)"
        )
        md_prod_action = "Admin → Deploy walkthrough → Maryland production runbook — resolve blockers"
    else:
        md_prod_status = "warning"
        md_prod_detail = (
            f"Maryland production partial — {md_prod_summary['ready']} ready, "
            f"{md_prod_summary['warnings']} warning(s); "
            f"live scrapers {md_prod_summary['live_scrapers_live_count']}/5"
        )
        md_prod_action = "Complete live scraper go-live, disable mock adapters, and set PUBLIC_BASE_URL"
    items.append(
        DeployCheckItem(
            id="maryland_production",
            title="Maryland production readiness",
            status=md_prod_status,
            detail=md_prod_detail,
            action=md_prod_action,
        )
    )

    from app.services.twilio_sms_production_runbook import build_twilio_sms_production_runbook

    sms_production = build_twilio_sms_production_runbook(db)
    sms_summary = sms_production["summary"]
    if sms_production["production_ready"]:
        sms_prod_status = "ready"
        sms_prod_detail = "Twilio live SMS production ready — outbound, inbound webhook, and signatures configured"
        sms_prod_action = None
    elif sms_summary["blocked"] > 0:
        sms_prod_status = "blocked"
        sms_prod_detail = (
            f"Live SMS blocked — {sms_summary['blocked']} blocker(s), {sms_summary['warnings']} warning(s)"
        )
        sms_prod_action = "Admin → Integrations → Copy Twilio go-live .env and wire Twilio Console webhook"
    else:
        sms_prod_status = "warning"
        sms_prod_detail = (
            f"Live SMS partial — {sms_summary['ready']} ready, {sms_summary['warnings']} warning(s)"
        )
        sms_prod_action = "Set SMS_DRY_RUN=false, PUBLIC_BASE_URL, and TWILIO_VALIDATE_SIGNATURES=true"
    items.append(
        DeployCheckItem(
            id="live_sms_production",
            title="Live SMS production",
            status=sms_prod_status,
            detail=sms_prod_detail,
            action=sms_prod_action,
        )
    )

    from app.services.maryland_launch_capstone import build_maryland_launch_capstone

    launch_capstone = build_maryland_launch_capstone(db)
    launch_summary = launch_capstone["summary"]
    if launch_capstone["launch_ready"]:
        launch_status = "ready"
        launch_detail = "Maryland launch capstone green — Maryland production and live SMS both ready for go-live"
        launch_action = None
    elif launch_summary["blocked"] > 0:
        launch_status = "blocked"
        launch_detail = (
            f"Maryland launch blocked — {launch_summary['blocked']} blocker(s), "
            f"{launch_summary['warnings']} warning(s)"
        )
        launch_action = "Admin → Deploy → Maryland launch capstone — resolve blockers in both runbooks"
    else:
        launch_status = "warning"
        launch_detail = (
            f"Maryland launch partial — {launch_summary['ready']} ready, "
            f"{launch_summary['warnings']} warning(s)"
        )
        launch_action = "Complete Maryland production and live SMS runbooks, then run launch smoke"
    items.append(
        DeployCheckItem(
            id="maryland_launch_capstone",
            title="Maryland launch capstone",
            status=launch_status,
            detail=launch_detail,
            action=launch_action,
        )
    )

    from app.services.production_ops_dashboard import build_production_ops_dashboard

    ops_dashboard = build_production_ops_dashboard(db)
    ops_summary = ops_dashboard["summary"]
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
            f"{ops_summary['warnings']} warning(s); "
            f"workers running {ops_summary['workers_running_count']}/4"
        )
        ops_action = "Enable background workers, probe live scrapers, and confirm launch capstone"
    items.append(
        DeployCheckItem(
            id="production_ops_dashboard",
            title="Production ops dashboard",
            status=ops_status,
            detail=ops_detail,
            action=ops_action,
        )
    )

    from app.services.production_perfection_capstone import build_production_perfection_capstone

    perfection_capstone = build_production_perfection_capstone(db)
    perfection_summary = perfection_capstone["summary"]
    if perfection_capstone["production_perfection_ready"]:
        perfection_status = "ready"
        perfection_detail = "Production perfection green — ops dashboard and Maryland launch both ready for go-live"
        perfection_action = None
    elif perfection_summary["blocked"] > 0:
        perfection_status = "blocked"
        perfection_detail = (
            f"Production perfection blocked — {perfection_summary['blocked']} blocker(s), "
            f"{perfection_summary['warnings']} warning(s)"
        )
        perfection_action = "Admin → Production perfection → Run production perfection check"
    else:
        perfection_status = "warning"
        perfection_detail = (
            f"Production perfection partial — {perfection_summary['ready']} ready, "
            f"{perfection_summary['warnings']} warning(s)"
        )
        perfection_action = "Complete ops dashboard and Maryland launch capstone, then run perfection check"
    items.append(
        DeployCheckItem(
            id="production_perfection",
            title="Production perfection",
            status=perfection_status,
            detail=perfection_detail,
            action=perfection_action,
        )
    )

    from app.services.production_launch_ceremony import build_production_launch_ceremony

    launch_ceremony = build_production_launch_ceremony(db)
    ceremony_summary = launch_ceremony["summary"]
    if launch_ceremony["launch_ceremony_ready"]:
        ceremony_status = "ready"
        ceremony_detail = "Production launch ceremony green — perfection, deploy bundle, and sign-off document ready"
        ceremony_action = None
    elif ceremony_summary["blocked"] > 0:
        ceremony_status = "blocked"
        ceremony_detail = (
            f"Launch ceremony blocked — {ceremony_summary['blocked']} blocker(s), "
            f"{ceremony_summary['warnings']} warning(s)"
        )
        ceremony_action = "Admin → Production launch ceremony → Run launch ceremony after perfection is green"
    else:
        ceremony_status = "warning"
        ceremony_detail = (
            f"Launch ceremony partial — {ceremony_summary['ready']} ready, "
            f"{ceremony_summary['warnings']} warning(s)"
        )
        ceremony_action = "Run production perfection check, then run launch ceremony for stakeholder sign-off"
    items.append(
        DeployCheckItem(
            id="production_launch_ceremony",
            title="Production launch ceremony",
            status=ceremony_status,
            detail=ceremony_detail,
            action=ceremony_action,
        )
    )

    from app.services.production_go_live_record import build_production_go_live_record

    go_live_record = build_production_go_live_record(db)
    go_live_summary = go_live_record["summary"]
    if go_live_record["production_go_live_record_ready"]:
        go_live_status = "ready"
        go_live_detail = "Production go-live record sealed — immutable launch archive with ceremony + health snapshot"
        go_live_action = None
    elif go_live_summary["blocked"] > 0:
        go_live_status = "blocked"
        go_live_detail = (
            f"Go-live record blocked — {go_live_summary['blocked']} blocker(s), "
            f"{go_live_summary['warnings']} warning(s)"
        )
        go_live_action = "Admin → Production go-live record → Seal launch record after ceremony is green"
    else:
        go_live_status = "warning"
        go_live_detail = (
            f"Go-live record partial — {go_live_summary['ready']} ready, "
            f"{go_live_summary['warnings']} warning(s); seal required"
        )
        go_live_action = "Run launch ceremony, then Admin → Production go-live record → Seal launch record"
    items.append(
        DeployCheckItem(
            id="production_go_live_record",
            title="Production go-live record",
            status=go_live_status,
            detail=go_live_detail,
            action=go_live_action,
        )
    )

    from app.services.production_launch_attestation import build_production_launch_attestation

    launch_attestation = build_production_launch_attestation(db)
    attestation_summary = launch_attestation["summary"]
    if launch_attestation["production_launch_attestation_ready"]:
        attestation_status = "ready"
        attestation_detail = (
            "Production launch attestation complete — SHA-256 digest archived for compliance sign-off"
        )
        attestation_action = None
    elif attestation_summary["blocked"] > 0:
        attestation_status = "blocked"
        attestation_detail = (
            f"Launch attestation blocked — {attestation_summary['blocked']} blocker(s), "
            f"{attestation_summary['warnings']} warning(s)"
        )
        attestation_action = "Admin → Production launch attestation → Attest launch after go-live record is sealed"
    else:
        attestation_status = "warning"
        attestation_detail = (
            f"Launch attestation partial — {attestation_summary['ready']} ready, "
            f"{attestation_summary['warnings']} warning(s); attest required"
        )
        attestation_action = "Seal go-live record, then Admin → Production launch attestation → Attest launch"
    items.append(
        DeployCheckItem(
            id="production_launch_attestation",
            title="Production launch attestation",
            status=attestation_status,
            detail=attestation_detail,
            action=attestation_action,
        )
    )

    from app.services.production_launch_perfection_seal import build_production_launch_perfection_seal

    perfection_seal = build_production_launch_perfection_seal(db)
    perfection_seal_summary = perfection_seal["summary"]
    if perfection_seal["production_launch_perfection_ready"]:
        perfection_seal_status = "ready"
        perfection_seal_detail = (
            "Production launch perfection sealed — ceremony, go-live record, and attestation chained"
        )
        perfection_seal_action = None
    elif perfection_seal_summary["blocked"] > 0:
        perfection_seal_status = "blocked"
        perfection_seal_detail = (
            f"Launch perfection seal blocked — {perfection_seal_summary['blocked']} blocker(s), "
            f"{perfection_seal_summary['warnings']} warning(s)"
        )
        perfection_seal_action = (
            "Admin → Production launch perfection seal → Seal launch perfection after perfection is green"
        )
    else:
        perfection_seal_status = "warning"
        perfection_seal_detail = (
            f"Launch perfection seal partial — {perfection_seal_summary['ready']} ready, "
            f"{perfection_seal_summary['warnings']} warning(s); one-click seal required"
        )
        perfection_seal_action = "Admin → Production launch perfection seal → Seal launch perfection"
    items.append(
        DeployCheckItem(
            id="production_launch_perfection_seal",
            title="Production launch perfection seal",
            status=perfection_seal_status,
            detail=perfection_seal_detail,
            action=perfection_seal_action,
        )
    )

    launch_archive = None
    launch_archive_summary: dict | None = None
    if include_launch_archive:
        from app.services.production_launch_archive import build_production_launch_archive

        launch_archive = build_production_launch_archive(db)
        launch_archive_summary = launch_archive["summary"]
        if launch_archive["production_launch_archive_ready"]:
            archive_status = "ready"
            archive_detail = (
                "Production launch archive complete — deploy bundle manifest with SHA-256 checksums archived"
            )
            archive_action = None
        elif launch_archive_summary["blocked"] > 0:
            archive_status = "blocked"
            archive_detail = (
                f"Launch archive blocked — {launch_archive_summary['blocked']} blocker(s), "
                f"{launch_archive_summary['warnings']} warning(s)"
            )
            archive_action = (
                "Admin → Production launch archive → Archive launch after perfection seal completes"
            )
        else:
            archive_status = "warning"
            archive_detail = (
                f"Launch archive partial — {launch_archive_summary['ready']} ready, "
                f"{launch_archive_summary['warnings']} warning(s); archive required"
            )
            archive_action = "Seal launch perfection, then Admin → Production launch archive → Archive launch"
        items.append(
            DeployCheckItem(
                id="production_launch_archive",
                title="Production launch archive",
                status=archive_status,
                detail=archive_detail,
                action=archive_action,
            )
        )

    launch_finale = None
    launch_finale_summary: dict | None = None
    if include_launch_finale:
        from app.services.production_launch_finale import build_production_launch_finale

        launch_finale = build_production_launch_finale(db)
        launch_finale_summary = launch_finale["summary"]
        if launch_finale["production_launch_finale_ready"]:
            finale_status = "ready"
            finale_detail = (
                "Production launch perfection finale complete — perfection seal and archive chained"
            )
            finale_action = None
        elif launch_finale_summary["blocked"] > 0:
            finale_status = "blocked"
            finale_detail = (
                f"Launch finale blocked — {launch_finale_summary['blocked']} blocker(s), "
                f"{launch_finale_summary['warnings']} warning(s)"
            )
            finale_action = (
                "Admin → Production launch perfection finale → Run launch finale after perfection is green"
            )
        else:
            finale_status = "warning"
            finale_detail = (
                f"Launch finale partial — {launch_finale_summary['ready']} ready, "
                f"{launch_finale_summary['warnings']} warning(s); one-click finale required"
            )
            finale_action = "Admin → Production launch perfection finale → Run launch finale"
        items.append(
            DeployCheckItem(
                id="production_launch_finale",
                title="Production launch perfection finale",
                status=finale_status,
                detail=finale_detail,
                action=finale_action,
            )
        )

    launch_bundle_verification = None
    launch_bundle_verification_summary: dict | None = None
    if include_launch_bundle_verification:
        from app.services.production_launch_perfection_manifest import (
            build_production_launch_perfection_manifest,
        )

        launch_bundle_verification = build_production_launch_perfection_manifest(db)
        launch_bundle_verification_summary = launch_bundle_verification["summary"]
        if launch_bundle_verification["production_launch_bundle_verified_ready"]:
            verify_status = "ready"
            verify_detail = (
                "Production launch bundle verified — all archived checksums match deploy bundle inventory"
            )
            verify_action = None
        elif launch_bundle_verification_summary["blocked"] > 0:
            verify_status = "blocked"
            verify_detail = (
                f"Launch bundle verification blocked — {launch_bundle_verification_summary['blocked']} blocker(s), "
                f"{launch_bundle_verification_summary['warnings']} warning(s)"
            )
            verify_action = (
                "Admin → Production launch perfection manifest → Verify launch bundle after finale completes"
            )
        else:
            verify_status = "warning"
            verify_detail = (
                f"Launch bundle verification partial — {launch_bundle_verification_summary['ready']} ready, "
                f"{launch_bundle_verification_summary['warnings']} warning(s); integrity sign-off required"
            )
            verify_action = "Admin → Production launch perfection manifest → Verify launch bundle"
        items.append(
            DeployCheckItem(
                id="production_launch_bundle_verification",
                title="Production launch bundle verification",
                status=verify_status,
                detail=verify_detail,
                action=verify_action,
            )
        )

    states = supported_states()
    multistate_ok = all(code in states for code in ("MD", "VA", "PA", "DE", "NJ"))
    items.append(
        DeployCheckItem(
            id="supported_states",
            title="Mid-Atlantic coverage",
            status="ready" if multistate_ok else "warning",
            detail=f"SUPPORTED_STATES={','.join(states)}",
            action=None if multistate_ok else "Set SUPPORTED_STATES=MD,VA,DC,PA,DE,NJ in .env",
        )
    )

    cms_nh_url = str(settings.CMS_NURSING_HOMES_API_URL or "").strip()
    cms_hh_url = str(settings.CMS_HOME_HEALTH_API_URL or "").strip()
    cms_post_acute_ok = cms_nh_url.startswith("https://data.cms.gov/") and cms_hh_url.startswith(
        "https://data.cms.gov/"
    )
    items.append(
        DeployCheckItem(
            id="cms_post_acute_scrape",
            title="CMS post-acute scrape URLs",
            status="ready" if cms_post_acute_ok else "warning",
            detail=(
                "Nursing homes + home health CMS datastore endpoints configured"
                if cms_post_acute_ok
                else "Set CMS_NURSING_HOMES_API_URL and CMS_HOME_HEALTH_API_URL"
            ),
            action=None
            if cms_post_acute_ok
            else "Use CMS Provider Data API URLs for SNF (4pq5-n9py) and HH (6jpm-sxkc)",
        )
    )

    demo_health_status = "pending"
    demo_health_label = "NOT CHECKED"
    demo_present_facility_count: int | None = None
    demo_broadcasting_count: int | None = None
    demo_expected_facility_count: int | None = None
    demo_walkthrough_intact_value: bool | None = None
    demo_active_gates: list[str] = []
    demo_gate_count: int | None = None
    demo_gates_snapshot: dict | None = None
    demo_item_status = "pending"
    demo_item_detail = "Run full demo setup to load the Mid-Atlantic demo environment"
    demo_item_action = "Admin → Run full demo setup"
    if db_ok:
        try:
            demo_status = build_demo_environment_status(db)
            health = demo_status["health"]
            demo_health_status = str(health["status"])
            demo_health_label = str(health["label"])
            demo_present_facility_count = int(demo_status["present_facility_count"])
            demo_broadcasting_count = int(demo_status["facility_count"])
            demo_expected_facility_count = int(demo_status["expected_facility_count"])
            demo_gates_snapshot = build_demo_gates_summary(db)
            demo_walkthrough_intact_value = demo_gates_snapshot["walkthrough_intact"]
            demo_active_gates = demo_gates_snapshot["active_gates"]
            demo_gate_count = demo_gates_snapshot["gate_count"]
            demo_item_detail = str(health["summary"])
            issues = list(health.get("issues") or [])
            if issues:
                issue_preview = "; ".join(issues[:3])
                if len(issues) > 3:
                    issue_preview += f" (+{len(issues) - 3} more)"
                demo_item_detail = f"{health['summary']} — {issue_preview}"
            facility_summary = (
                f"{demo_present_facility_count}/{demo_expected_facility_count} present, "
                f"{demo_broadcasting_count}/{demo_expected_facility_count} broadcasting"
            )
            demo_item_detail = f"{demo_item_detail} ({facility_summary})"
            if demo_active_gates:
                demo_item_detail = f"{demo_item_detail}; active gates: {', '.join(demo_active_gates)}"
            if demo_gate_count:
                demo_item_detail = f"{demo_item_detail}; confirmation gates: {demo_gate_count}"
            demo_item_detail = (
                f"{demo_item_detail}; admin actions: {len(DEMO_ADMIN_ACTION_DEMO_GATES)}"
            )
            if health["status"] == "green":
                demo_item_status = "ready"
                demo_item_action = None
            elif health["status"] == "yellow":
                demo_item_status = "warning"
                demo_item_action = "Admin → Demo environment panel — resolve issues or run full demo setup"
            else:
                demo_item_status = "blocked"
                demo_item_action = "Admin → Run full demo setup"
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            demo_item_status = "pending"
            demo_item_detail = f"Could not inspect demo environment: {exc}"
    else:
        demo_item_detail = "Connect database first, then run full demo setup"

    items.append(
        DeployCheckItem(
            id="demo_environment",
            title="Demo environment health",
            status=demo_item_status,
            detail=demo_item_detail,
            action=demo_item_action,
        )
    )

    blocked = sum(1 for row in items if row.status == "blocked")
    warnings = sum(1 for row in items if row.status == "warning")
    ready = sum(1 for row in items if row.status == "ready")
    sms_blocked = sum(
        1 for row in items if row.status == "blocked" and row.id not in {"demo_environment"}
    )
    live_ready = live_sms and public_ok and twilio_cfg and sms_blocked == 0

    return {
        "summary": {
            "ready": ready,
            "warnings": warnings,
            "blocked": blocked,
            "live_sms_ready": live_ready,
            "demo_health_status": demo_health_status,
            "demo_health_label": demo_health_label,
            "demo_present_facility_count": demo_present_facility_count,
            "demo_broadcasting_count": demo_broadcasting_count,
            "demo_expected_facility_count": demo_expected_facility_count,
            "demo_walkthrough_intact": demo_walkthrough_intact_value,
            "demo_active_gates": demo_active_gates,
            "demo_gate_count": demo_gate_count,
            "demo_admin_action_count": len(DEMO_ADMIN_ACTION_DEMO_GATES),
            "docker_compose_command": "docker compose up -d --build",
            "health_url": f"{public_base}/health" if public_base else "/health",
            "admin_url": f"{public_base}/admin" if public_base else "/admin",
            "maryland_production_ready": md_production["production_ready"],
            "maryland_production_ready_count": md_prod_summary["ready"],
            "maryland_production_warning_count": md_prod_summary["warnings"],
            "maryland_production_blocked_count": md_prod_summary["blocked"],
            "live_scrapers_all_live": md_prod_summary["live_scrapers_all_live"],
            "live_sms_ready": sms_production["live_sms_ready"],
            "twilio_sms_production_ready": sms_production["production_ready"],
            "maryland_launch_ready": launch_capstone["launch_ready"],
            "maryland_launch_ready_count": launch_summary["ready"],
            "maryland_launch_warning_count": launch_summary["warnings"],
            "maryland_launch_blocked_count": launch_summary["blocked"],
            "production_ops_ready": ops_dashboard["production_ops_ready"],
            "production_ops_ready_count": ops_summary["ready"],
            "production_ops_warning_count": ops_summary["warnings"],
            "production_ops_blocked_count": ops_summary["blocked"],
            "production_perfection_ready": perfection_capstone["production_perfection_ready"],
            "production_perfection_ready_count": perfection_summary["ready"],
            "production_perfection_warning_count": perfection_summary["warnings"],
            "production_perfection_blocked_count": perfection_summary["blocked"],
            "production_launch_ceremony_ready": launch_ceremony["launch_ceremony_ready"],
            "production_launch_ceremony_ready_count": ceremony_summary["ready"],
            "production_launch_ceremony_warning_count": ceremony_summary["warnings"],
            "production_launch_ceremony_blocked_count": ceremony_summary["blocked"],
            "production_go_live_record_ready": go_live_record["production_go_live_record_ready"],
            "production_go_live_record_ready_count": go_live_summary["ready"],
            "production_go_live_record_warning_count": go_live_summary["warnings"],
            "production_go_live_record_blocked_count": go_live_summary["blocked"],
            "production_launch_attestation_ready": launch_attestation["production_launch_attestation_ready"],
            "production_launch_attestation_ready_count": attestation_summary["ready"],
            "production_launch_attestation_warning_count": attestation_summary["warnings"],
            "production_launch_attestation_blocked_count": attestation_summary["blocked"],
            "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
            "production_launch_perfection_ready_count": perfection_seal_summary["ready"],
            "production_launch_perfection_warning_count": perfection_seal_summary["warnings"],
            "production_launch_perfection_blocked_count": perfection_seal_summary["blocked"],
            "production_launch_archive_ready": launch_archive["production_launch_archive_ready"]
            if launch_archive is not None
            else None,
            "production_launch_archive_ready_count": launch_archive_summary["ready"]
            if launch_archive_summary is not None
            else None,
            "production_launch_archive_warning_count": launch_archive_summary["warnings"]
            if launch_archive_summary is not None
            else None,
            "production_launch_archive_blocked_count": launch_archive_summary["blocked"]
            if launch_archive_summary is not None
            else None,
            "production_launch_finale_ready": launch_finale["production_launch_finale_ready"]
            if launch_finale is not None
            else None,
            "production_launch_finale_ready_count": launch_finale_summary["ready"]
            if launch_finale_summary is not None
            else None,
            "production_launch_finale_warning_count": launch_finale_summary["warnings"]
            if launch_finale_summary is not None
            else None,
            "production_launch_finale_blocked_count": launch_finale_summary["blocked"]
            if launch_finale_summary is not None
            else None,
            "production_launch_bundle_verified_ready": launch_bundle_verification[
                "production_launch_bundle_verified_ready"
            ]
            if launch_bundle_verification is not None
            else None,
            "production_launch_bundle_verified_ready_count": launch_bundle_verification_summary["ready"]
            if launch_bundle_verification_summary is not None
            else None,
            "production_launch_bundle_verified_warning_count": launch_bundle_verification_summary["warnings"]
            if launch_bundle_verification_summary is not None
            else None,
            "production_launch_bundle_verified_blocked_count": launch_bundle_verification_summary["blocked"]
            if launch_bundle_verification_summary is not None
            else None,
        },
        "demo_gates": demo_gates_snapshot,
        "demo_admin_actions": list(DEMO_ADMIN_ACTION_DEMO_GATES),
        "twilio_console_steps": [
            "Twilio Console → Phone Numbers → Manage → Active numbers → select your OfferCare number",
            "Messaging configuration → A MESSAGE COMES IN → Webhook",
            f"Set URL to: {webhook_url or '<PUBLIC_BASE_URL>/shift-sniper/twilio/sms'}",
            "HTTP method: POST",
            "Save — clinicians can reply YES to lock shifts",
        ],
        "portal_steps": [
            "Clinicians open /portal on mobile and sign in",
            "Tap Enable push alerts after VAPID keys are configured",
            "Matched-shift pushes open /portal/?offer=… to highlight the Lock button",
            "Install to home screen when prompted (PWA manifest + service worker)",
        ],
        "hospital_steps": [
            "Admin → Seed full demo environment to load all hospital + post-acute demos in one click",
            "Or Seed all hospital demos for ICU Shift Sniper tests in MD, VA, and NJ",
            "Notify top on Saint Jude's, Inova Fairfax, or Hackensack to test Shift Sniper ranking",
        ],
        "post_acute_steps": [
            "Admin → Seed full demo environment loads SNF across MD/VA/DC/PA/DE/NJ plus MD home health",
            "Or Seed all post-acute demos for SNF + home health without hospital ICUs",
            "Admin → Scrape MD nursing homes or home health (auto-creates CNA/LPN/RN shifts)",
            "Or run Scrape post-acute Mid-Atlantic to load SNF + HH across MD/VA/DC/PA/DE/NJ",
            "Seed VA nursing home demo to test cross-state SNF matching before live CMS scrape",
            "Seed DE or NJ nursing home demo to verify GNA shifts rank CNA in non-MD/DC states",
        ],
        "maryland_platform_steps": [
            "Worker inflow — share /join for Maryland CNA/LPN apply with instant MBON credentialing",
            "Admin → Maryland COMAR compliance — run expiration monitor and screen pending clinicians",
            "Admin → Scan Indeed / ZipRecruiter for crisis leads, then Draft outreach emails for DONs",
            "Admin → Poll VMS & create offers from ShiftWise / Fieldglass dry-run shifts",
            "Background scheduler polls VMS every 15 minutes and scans Indeed/ZipRecruiter daily",
            "Compliance monitor background scheduler sweeps document expirations hourly (COMPLIANCE_MONITOR_WORKER_ENABLED)",
            "Integrations panel → Live scrapers grid shows MBON, OIG, judiciary, job board, and VMS dry-run vs live-ready status",
            "Set LIVE_SCRAPER_GATEWAY_BASE_URL and flip *_DRY_RUN=false — Admin → Probe live scrapers to verify adapter health",
            "Ops panel → Run scheduler ticks to test cascade, VMS poll, job board scan, and compliance monitor without waiting for intervals",
            "Deploy walkthrough panel renders Maryland platform steps after refresh",
            "Shift Sniper ranks geo-matched, compliant aides and dispatches SMS within 5 minutes",
        ],
        "maryland_production_steps": md_production["steps"],
        "maryland_production_runbook": md_production,
        "live_sms_production_steps": sms_production["steps"],
        "twilio_sms_production_runbook": sms_production,
        "maryland_launch_capstone_steps": launch_capstone["steps"],
        "maryland_launch_capstone": launch_capstone,
        "production_ops_dashboard_steps": ops_dashboard["steps"],
        "production_ops_dashboard": ops_dashboard,
        "production_perfection_steps": perfection_capstone["steps"],
        "production_perfection_capstone": perfection_capstone,
        "production_launch_ceremony_steps": launch_ceremony["steps"],
        "production_launch_ceremony": launch_ceremony,
        "production_go_live_record_steps": go_live_record["steps"],
        "production_go_live_record": go_live_record,
        "production_launch_attestation_steps": launch_attestation["steps"],
        "production_launch_attestation": launch_attestation,
        "production_launch_perfection_seal_steps": perfection_seal["steps"],
        "production_launch_perfection_seal": perfection_seal,
        "production_launch_archive_steps": launch_archive["steps"] if launch_archive is not None else [],
        "production_launch_archive": launch_archive,
        "production_launch_finale_steps": launch_finale["steps"] if launch_finale is not None else [],
        "production_launch_finale": launch_finale,
        "production_launch_bundle_verification_steps": launch_bundle_verification["steps"]
        if launch_bundle_verification is not None
        else [],
        "production_launch_bundle_verification": launch_bundle_verification,
        "demo_steps": [
            "Admin → Run full demo setup auto-resets locked shifts, then seeds 10 facilities, portal logins, push subs, and matched alerts",
            "Copy demo walkthrough script for a presenter-ready markdown guide with deep links per shift",
            "Or download demo walkthrough (.md) for slides, notes, or sharing with presenters",
            "Or Seed full demo environment when you only need facilities and portal logins without push/notify",
            "Admin → Demo environment panel — confirm loaded shifts and matched clinician counts",
            "Deploy checklist auto-checks demo environment health — green ready, yellow partial, red run full demo setup",
            "Deploy walkthrough summary shows demo present vs broadcasting facility counts",
            "Deploy walkthrough summary shows demo walkthrough intact status and active confirmation gates",
            "Deploy walkthrough summary shows demo confirmation gate count alongside active gates",
            "Deploy walkthrough summary shows demo admin action count alongside confirmation gates",
            "Deploy walkthrough panel renders the embedded demo_gates gate matrix after refresh",
            "Deploy walkthrough panel renders the embedded demo admin actions catalog alongside the gate matrix",
            "Deploy walkthrough panel gate matrix header shows demo admin action count alongside gate count",
            "Demo environment panel renders the embedded demo_gates gate matrix after refresh",
            "Demo environment panel renders the embedded demo admin actions catalog alongside the gate matrix",
            "Demo environment panel gate matrix header shows demo admin action count alongside gate count",
            "Export demo status JSON embeds the full demo_gates snapshot for structured gate sign-off",
            "Demo status JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Demo status JSON includes top-level demo_admin_action_count alongside demo_admin_actions",
            "Demo status CSV includes demo gate summary and gate matrix sections",
            "Demo and deploy bundles include demo status JSON/CSV with embedded demo_gates for offline gate sign-off",
            "Deploy bundle checklist JSON/CSV includes the embedded demo_gates snapshot for offline deploy sign-off",
            "Run full demo setup returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "Reset demo environment returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "Per-row Reset returns status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "Lock test returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "Notify matched returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "Ensure demo portal logins returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "Ensure demo push subscriptions returns demo_status with the embedded demo_gates gate matrix, demo_admin_action_count, and demo_admin_actions catalog",
            "All demo admin actions return embedded demo_gates with demo_admin_action_count and the demo_admin_actions catalog — the gate matrix refreshes immediately after setup, reset, lock test, notify, and ensure actions",
            "Deploy checklist CSV includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Deploy checklist JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Demo gates JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Demo gates JSON includes demo admin action count alongside gate count",
            "Download demo gates (.txt) includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Demo health badge shows present vs broadcasting facility counts alongside status and issues",
            "Demo health badge shows demo admin action count alongside confirmation gate count",
            "Check the demo health badge — green ready, yellow partial, red needs full demo setup",
            "Export demo status as JSON or CSV for QA checklists and walkthrough sign-off",
            "Or download demo bundle (.zip) for walkthrough markdown, gates JSON, and status exports together",
            "Demo-ready gate warns before copying or downloading walkthrough, portal links, or bundle when health is not green",
            "Demo-ready gate also warns before Run full demo setup when health is not green",
            "Demo-ready reset gate warns before Reset demo environment when health is green",
            "Demo health badge summarizes which admin actions require confirmation gates",
            "Per-row Reset asks for confirmation when unlocking a locked shift during an intact walkthrough",
            "Lock test asks for confirmation when locking a broadcasting shift during an intact walkthrough",
            "Notify matched asks for confirmation when sending push alerts during an intact walkthrough",
            "Ensure demo portal logins asks for confirmation when resetting passwords during an intact walkthrough",
            "Ensure demo push subscriptions asks for confirmation when registering push subs during an intact walkthrough",
            "Copy demo portal links asks for confirmation when demo health is not green",
            "GET /api/seed/demo-gates returns active confirmation gates and the full gate matrix",
            "Admin → Export gates (.json) in the Demo environment panel for the confirmation gate matrix",
            "Demo walkthrough markdown includes the full confirmation gate matrix with active/inactive status per gate",
            "Admin → Copy active gates in the Demo environment panel for a presenter-ready gate matrix snapshot with the demo admin actions catalog",
            "Demo clinicians sign in at /portal with @offercare.demo email and password SecretPass1",
            "Admin → Ensure demo push subscriptions so matched alerts work without a real browser device",
            "Clinicians can also enable live push at /portal after VAPID keys are configured",
            "Admin → Notify matched on all demos to push every loaded shift in one click",
            "Open demo portal deep links — portal pre-fills the matched @offercare.demo clinician login",
            "Portal warns if you sign in as the wrong demo clinician for a deep-linked shift",
            "Smoke test demo lock to verify lock + placement ledger without opening /portal",
            "Or use Lock test on a specific demo shift row to verify one facility at a time",
            "Or use Notify on a specific demo shift row to test matched push alerts for one facility",
            "Or use Reset on a locked demo shift row to unlock one facility without resetting all 10 demos",
            "Locked demo rows keep LOCKED status and per-row Reset visible after lock test even when loaded is false",
            "Demo health counts locked rows as present — only truly missing shifts lower the facility count",
            "Per-row Reset returns a broadcasting offer_row snapshot so Lock test and Notify reappear after unlock",
            "Reset demo environment to unlock shifts and clear placements before the next walkthrough",
            "Or notify matched per shift from Open shifts",
        ],
        "export_steps": [
            "Export deploy checklist as JSON or CSV for production sign-off",
            "Deploy checklist JSON embeds the full demo_gates snapshot for structured gate sign-off",
            "Deploy checklist JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Deploy bundle demo status JSON/CSV includes the embedded demo_gates snapshot",
            "Demo status JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Deploy bundle checklist JSON/CSV includes the embedded demo_gates snapshot",
            "Deploy checklist CSV includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Download deploy bundle (.zip) for checklist exports plus demo walkthrough, gates, and status together",
            "Or download demo gates JSON via GET /api/seed/demo-gates.json for QA sign-off without the full bundle",
            "Demo gates JSON includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Demo gates JSON includes demo admin action count alongside gate count",
            "Or download demo gates (.txt) via GET /api/seed/demo-gates.txt for a copy/paste gate matrix snapshot",
            "Demo gates (.txt) includes the demo admin actions catalog with embedded demo_gates endpoints",
            "Deploy panel → Copy active gates or Download gates (.txt) for demo gate QA with the demo admin actions catalog",
            "Deploy panel → Export gates (.json) or Download gates (.txt) toasts show demo admin action count",
            "Deploy panel → Export gates (.json) for structured demo gate sign-off alongside deploy checklist exports",
            "Deploy walkthrough panel renders Maryland platform steps after refresh",
            "Deploy walkthrough panel renders Maryland production runbook after refresh",
            "Deploy walkthrough panel renders Twilio live SMS production steps after refresh",
        ],
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "detail": row.detail,
                "action": row.action,
            }
            for row in items
        ],
    }


def build_deploy_checklist_json(
    db: Session,
    *,
    include_launch_archive: bool = True,
    include_launch_finale: bool = True,
    include_launch_bundle_verification: bool = True,
) -> dict:
    snapshot = build_deploy_checklist(
        db,
        include_launch_archive=include_launch_archive,
        include_launch_finale=include_launch_finale,
        include_launch_bundle_verification=include_launch_bundle_verification,
    )
    return {
        "filename": DEPLOY_CHECKLIST_JSON_FILENAME,
        "content": json.dumps(snapshot, indent=2),
    }


def build_deploy_checklist_csv(
    db: Session,
    *,
    include_launch_archive: bool = True,
    include_launch_finale: bool = True,
    include_launch_bundle_verification: bool = True,
) -> dict:
    snapshot = build_deploy_checklist(
        db,
        include_launch_archive=include_launch_archive,
        include_launch_finale=include_launch_finale,
        include_launch_bundle_verification=include_launch_bundle_verification,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    summary = snapshot["summary"]
    writer.writerow(["DEPLOY CHECKLIST SUMMARY"])
    writer.writerow(["metric", "value"])
    for key, value in summary.items():
        writer.writerow([key, value])
    writer.writerow([])
    writer.writerow(["DEPLOY ITEMS"])
    writer.writerow(["id", "title", "status", "detail", "action"])
    for row in snapshot["items"]:
        writer.writerow(
            [
                row["id"],
                row["title"],
                row["status"],
                row["detail"],
                row.get("action") or "",
            ]
        )
    demo_gates = snapshot.get("demo_gates")
    if demo_gates:
        writer.writerow([])
        writer.writerow(["DEMO GATES"])
        writer.writerow(["metric", "value"])
        writer.writerow(["walkthrough_intact", demo_gates["walkthrough_intact"]])
        writer.writerow(["health_status", demo_gates["health_status"]])
        writer.writerow(["health_label", demo_gates["health_label"]])
        writer.writerow(["gate_count", demo_gates["gate_count"]])
        writer.writerow(["demo_admin_action_count", demo_gates["demo_admin_action_count"]])
        writer.writerow(["active_gates", ", ".join(demo_gates["active_gates"])])
        writer.writerow([])
        writer.writerow(["DEMO GATE MATRIX"])
        writer.writerow(["id", "action", "confirm_when", "active"])
        for row in demo_gates["gates"]:
            writer.writerow([row["id"], row["action"], row["confirm_when"], row["active"]])
        append_demo_admin_actions_csv(writer)
    for section_name, steps_key in (
        ("TWILIO CONSOLE STEPS", "twilio_console_steps"),
        ("PORTAL STEPS", "portal_steps"),
        ("HOSPITAL STEPS", "hospital_steps"),
        ("POST ACUTE STEPS", "post_acute_steps"),
        ("MARYLAND PLATFORM STEPS", "maryland_platform_steps"),
        ("MARYLAND PRODUCTION STEPS", "maryland_production_steps"),
        ("LIVE SMS PRODUCTION STEPS", "live_sms_production_steps"),
        ("MARYLAND LAUNCH CAPSTONE STEPS", "maryland_launch_capstone_steps"),
        ("PRODUCTION OPS DASHBOARD STEPS", "production_ops_dashboard_steps"),
        ("PRODUCTION PERFECTION STEPS", "production_perfection_steps"),
        ("PRODUCTION LAUNCH CEREMONY STEPS", "production_launch_ceremony_steps"),
        ("PRODUCTION GO-LIVE RECORD STEPS", "production_go_live_record_steps"),
        ("PRODUCTION LAUNCH ATTESTATION STEPS", "production_launch_attestation_steps"),
        ("PRODUCTION LAUNCH PERFECTION SEAL STEPS", "production_launch_perfection_seal_steps"),
        ("PRODUCTION LAUNCH ARCHIVE STEPS", "production_launch_archive_steps"),
        ("PRODUCTION LAUNCH PERFECTION FINALE STEPS", "production_launch_finale_steps"),
        ("PRODUCTION LAUNCH BUNDLE VERIFICATION STEPS", "production_launch_bundle_verification_steps"),
        ("DEMO STEPS", "demo_steps"),
    ):
        writer.writerow([])
        writer.writerow([section_name])
        writer.writerow(["step"])
        for step in snapshot.get(steps_key) or []:
            writer.writerow([step])
    return {
        "filename": DEPLOY_CHECKLIST_CSV_FILENAME,
        "content": buffer.getvalue(),
    }


def _artifact_bytes(content: str | bytes) -> bytes:
    if isinstance(content, bytes):
        return content
    return str(content).encode("utf-8")


def collect_deploy_bundle_artifacts(db: Session) -> list[dict[str, object]]:
    from app.services.production_launch_perfection_seal import build_production_launch_perfection_seal_json
    from app.services.production_launch_attestation import (
        build_production_launch_attestation_json,
        build_production_launch_attestation_markdown,
    )
    from app.services.production_go_live_record import build_production_go_live_record_json
    from app.services.production_launch_ceremony import (
        build_production_launch_ceremony_json,
        build_production_launch_ceremony_markdown,
    )
    from app.services.production_perfection_capstone import build_production_perfection_capstone_json
    from app.services.production_ops_dashboard import build_production_ops_dashboard_json
    from app.services.maryland_launch_capstone import build_maryland_launch_capstone_json
    from app.services.maryland_production_runbook import build_maryland_production_runbook_json
    from app.services.twilio_sms_production_runbook import build_twilio_sms_production_runbook_json

    checklist_json = build_deploy_checklist_json(
        db,
        include_launch_archive=False,
        include_launch_finale=False,
        include_launch_bundle_verification=False,
    )
    checklist_csv = build_deploy_checklist_csv(
        db,
        include_launch_archive=False,
        include_launch_finale=False,
        include_launch_bundle_verification=False,
    )
    walkthrough = build_demo_walkthrough_script(db)
    demo_json = build_demo_status_json(db)
    demo_csv = build_demo_status_csv(db)
    gates_json = build_demo_gates_json(db)
    gates_txt = build_demo_gates_txt(db)
    md_production_json = build_maryland_production_runbook_json(db)
    sms_production_json = build_twilio_sms_production_runbook_json(db)
    launch_capstone_json = build_maryland_launch_capstone_json(db)
    ops_dashboard_json = build_production_ops_dashboard_json(db)
    perfection_capstone_json = build_production_perfection_capstone_json(db)
    launch_ceremony_md = build_production_launch_ceremony_markdown(db)
    launch_ceremony_json = build_production_launch_ceremony_json(db)
    go_live_record_json = build_production_go_live_record_json(db)
    launch_attestation_md = build_production_launch_attestation_markdown(db)
    launch_attestation_json = build_production_launch_attestation_json(db)
    perfection_seal_json = build_production_launch_perfection_seal_json(db)
    snapshot = build_deploy_checklist(
        db,
        include_launch_archive=False,
        include_launch_finale=False,
        include_launch_bundle_verification=False,
    )
    summary = snapshot["summary"]
    gates = build_demo_gates_summary(db)
    readme = "\n".join(
        [
            "OfferCare Deploy Bundle",
            "",
            (
                f"Deploy checklist: {summary['ready']} ready, "
                f"{summary['warnings']} warnings, {summary['blocked']} blocked"
            ),
            f"Live SMS ready: {'yes' if summary['live_sms_ready'] else 'no'}",
            (
                f"Demo health: {summary.get('demo_health_label') or '—'} "
                f"({summary.get('demo_health_status') or 'pending'})"
            ),
            (
                f"Demo facilities: {summary.get('demo_present_facility_count', '—')}/"
                f"{summary.get('demo_expected_facility_count', '—')} present, "
                f"{summary.get('demo_broadcasting_count', '—')}/"
                f"{summary.get('demo_expected_facility_count', '—')} broadcasting"
            ),
            (
                f"Walkthrough intact: {'yes' if summary.get('demo_walkthrough_intact') else 'no' if summary.get('demo_walkthrough_intact') is False else '—'}"
            ),
            (
                f"Maryland production ready: {'yes' if summary.get('maryland_production_ready') else 'no'}"
            ),
            (
                f"Twilio SMS production ready: {'yes' if summary.get('twilio_sms_production_ready') else 'no'}"
            ),
            (
                f"Maryland launch ready: {'yes' if summary.get('maryland_launch_ready') else 'no'}"
            ),
            (
                f"Production ops ready: {'yes' if summary.get('production_ops_ready') else 'no'}"
            ),
            (
                f"Production perfection ready: {'yes' if summary.get('production_perfection_ready') else 'no'}"
            ),
            (
                f"Production launch ceremony ready: {'yes' if summary.get('production_launch_ceremony_ready') else 'no'}"
            ),
            (
                f"Production go-live record ready: {'yes' if summary.get('production_go_live_record_ready') else 'no'}"
            ),
            (
                f"Production launch attestation ready: {'yes' if summary.get('production_launch_attestation_ready') else 'no'}"
            ),
            (
                f"Production launch perfection ready: {'yes' if summary.get('production_launch_perfection_ready') else 'no'}"
            ),
            (
                f"Production launch archive ready: {'yes' if summary.get('production_launch_archive_ready') else 'no'}"
            ),
            (
                f"Production launch finale ready: {'yes' if summary.get('production_launch_finale_ready') else 'no'}"
            ),
            (
                f"Production launch bundle verified: {'yes' if summary.get('production_launch_bundle_verified_ready') else 'no'}"
            ),
            (
                f"Live SMS ready: {'yes' if summary.get('live_sms_ready') else 'no'}"
            ),
            (
                f"Live scrapers all live: {'yes' if summary.get('live_scrapers_all_live') else 'no'}"
            ),
            (
                f"Active gates: {', '.join(gates['active_gates'])}"
                if gates["active_gates"]
                else "Active gates: none"
            ),
            (
                f"Confirmation gates configured: {summary.get('demo_gate_count') or gates.get('gate_count') or '—'}"
            ),
            (
                f"Demo admin actions catalog: {summary.get('demo_admin_action_count') or len(DEMO_ADMIN_ACTION_DEMO_GATES)} actions"
            ),
            "",
            "Files:",
            f"- {checklist_json['filename']} — full deploy checklist snapshot with embedded demo_gates and demo admin actions catalog",
            f"- {checklist_csv['filename']} — QA spreadsheet for deploy sign-off with demo gate matrix",
            f"- {walkthrough['filename']} — demo walkthrough with portal deep links",
            f"- {gates_json['filename']} — demo confirmation gate matrix, active gates, and demo admin actions catalog",
            f"- {gates_txt['filename']} — copy/paste gate matrix snapshot with demo admin actions catalog",
            f"- {demo_json['filename']} — demo environment status with embedded demo_gates and demo admin actions catalog",
            f"- {demo_csv['filename']} — demo status spreadsheet with demo gate matrix",
            f"- {md_production_json['filename']} — Maryland production runbook with live scraper and launch checks",
            f"- {sms_production_json['filename']} — Twilio live SMS production runbook with webhook and lock-reply steps",
            f"- {launch_capstone_json['filename']} — Maryland launch capstone combining production runbooks and smoke steps",
            f"- {ops_dashboard_json['filename']} — production ops dashboard with workers, metrics, launch, and scraper signals",
            f"- {perfection_capstone_json['filename']} — production perfection capstone combining ops, launch, and smoke checks",
            f"- {launch_ceremony_md['filename']} — stakeholder launch ceremony sign-off markdown",
            f"- {launch_ceremony_json['filename']} — production launch ceremony snapshot JSON",
            f"- {go_live_record_json['filename']} — sealed production go-live record with ceremony run + health snapshot",
            f"- {launch_attestation_md['filename']} — compliance launch attestation with SHA-256 digest sign-off",
            f"- {launch_attestation_json['filename']} — production launch attestation snapshot JSON",
            f"- {perfection_seal_json['filename']} — production launch perfection seal chaining ceremony, go-live, and attestation",
            "- offercare-production-launch-archive.json — deploy bundle manifest with SHA-256 checksums for all launch artifacts",
            "- offercare-production-launch-finale.json — production launch perfection finale chaining seal and archive",
            "- offercare-production-launch-perfection-manifest.json — bundle integrity verification against archived checksums",
            "",
            "Generated from Admin → Deploy walkthrough panel.",
        ]
    )
    return [
        {"filename": checklist_json["filename"], "content": checklist_json["content"]},
        {"filename": checklist_csv["filename"], "content": checklist_csv["content"]},
        {"filename": walkthrough["filename"], "content": walkthrough["markdown"]},
        {"filename": gates_json["filename"], "content": gates_json["content"]},
        {"filename": gates_txt["filename"], "content": gates_txt["content"]},
        {"filename": demo_json["filename"], "content": demo_json["content"]},
        {"filename": demo_csv["filename"], "content": demo_csv["content"]},
        {"filename": md_production_json["filename"], "content": md_production_json["content"]},
        {"filename": sms_production_json["filename"], "content": sms_production_json["content"]},
        {"filename": launch_capstone_json["filename"], "content": launch_capstone_json["content"]},
        {"filename": ops_dashboard_json["filename"], "content": ops_dashboard_json["content"]},
        {"filename": perfection_capstone_json["filename"], "content": perfection_capstone_json["content"]},
        {"filename": launch_ceremony_md["filename"], "content": launch_ceremony_md["markdown"]},
        {"filename": launch_ceremony_json["filename"], "content": launch_ceremony_json["content"]},
        {"filename": go_live_record_json["filename"], "content": go_live_record_json["content"]},
        {"filename": launch_attestation_md["filename"], "content": launch_attestation_md["markdown"]},
        {"filename": launch_attestation_json["filename"], "content": launch_attestation_json["content"]},
        {"filename": perfection_seal_json["filename"], "content": perfection_seal_json["content"]},
        {"filename": DEPLOY_EXPORT_README_FILENAME, "content": readme},
    ]


def build_deploy_export_bundle(db: Session) -> dict:
    from app.services.production_launch_finale import build_production_launch_finale_json
    from app.services.production_launch_archive import build_production_launch_archive_json
    from app.services.production_launch_perfection_manifest import (
        build_production_launch_perfection_manifest_json,
    )

    artifacts = collect_deploy_bundle_artifacts(db)
    launch_archive_json = build_production_launch_archive_json(db)
    launch_finale_json = build_production_launch_finale_json(db)
    perfection_manifest_json = build_production_launch_perfection_manifest_json(db)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in artifacts:
            archive.writestr(str(row["filename"]), _artifact_bytes(row["content"]))
        archive.writestr(launch_archive_json["filename"], launch_archive_json["content"])
        archive.writestr(launch_finale_json["filename"], launch_finale_json["content"])
        archive.writestr(
            perfection_manifest_json["filename"],
            perfection_manifest_json["content"],
        )
    return {
        "filename": DEPLOY_EXPORT_ZIP_FILENAME,
        "content": buffer.getvalue(),
        "file_count": len(artifacts) + 3,
    }
