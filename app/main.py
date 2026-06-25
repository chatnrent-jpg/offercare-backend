from contextlib import asynccontextmanager
import asyncio
import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.live_scrapers import live_scrapers_summary
from app.services.maryland_launch_capstone import build_maryland_launch_capstone
from app.services.maryland_production_runbook import build_maryland_production_runbook
from app.services.production_ops_dashboard import build_production_ops_dashboard
from app.services.production_perfection_capstone import build_production_perfection_capstone
from app.services.production_launch_ceremony import build_production_launch_ceremony
from app.services.production_go_live_record import build_production_go_live_record
from app.services.production_launch_attestation import build_production_launch_attestation
from app.services.production_launch_perfection_seal import build_production_launch_perfection_seal
from app.services.production_launch_archive import build_production_launch_archive
from app.services.production_launch_finale import build_production_launch_finale
from app.services.production_launch_perfection_manifest import build_production_launch_perfection_manifest
from app.services.twilio_sms_production_runbook import build_twilio_sms_production_runbook
from app.services.states import grid_region_label
from app.services.vetted_infrastructure import build_vettedcare_infrastructure_readiness
from app.database import engine, get_db
import app.models  # noqa: F401 — register tables before migrations
from app.migrations import run_migrations
from app.logging_config import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.services.cascade_worker import start_cascade_worker, stop_cascade_worker
from app.services.compliance_scheduler import start_compliance_scheduler, stop_compliance_scheduler
from app.services.staffing_scheduler import start_staffing_scheduler, stop_staffing_scheduler
from app.runtime import register_asgi_app
from app.routers.deploy import router as deploy_router
from app.routers.ops import router as ops_router
from app.routers.integrations import router as integrations_router
from app.routers.clinicians import router as clinicians_router
from app.routers.core import router as core_router
from app.routers.scraper import router as scraper_router
from app.routers.shifts import router as shifts_router
from app.routers.shift_sniper import router as shift_sniper_router
from app.routers.compliance import router as compliance_router
from app.routers.landing import router as landing_router
from app.routers.live_scraper_adapters import router as live_scraper_adapters_router
from app.routers.outreach import router as outreach_router
from app.routers.vms import router as vms_router
from app.routers.vettedcare import router as vettedcare_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    register_asgi_app(app)
    try:
        run_migrations(engine)
        logger.info("Database migrations ready.")
    except Exception as exc:
        logger.warning("Database not ready — API online, tables not created: %s", exc)
    worker_stop = await start_cascade_worker()
    scheduler_stop = await start_staffing_scheduler()
    compliance_stop = await start_compliance_scheduler()
    try:
        yield
    finally:
        await stop_compliance_scheduler(compliance_stop)
        await stop_staffing_scheduler(scheduler_stop)
        await stop_cascade_worker(worker_stop)


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.include_router(core_router)
app.include_router(deploy_router)
app.include_router(ops_router)
app.include_router(integrations_router)
app.include_router(live_scraper_adapters_router)
app.include_router(clinicians_router)
app.include_router(scraper_router)
app.include_router(shifts_router)
app.include_router(shift_sniper_router)
app.include_router(compliance_router)
app.include_router(landing_router)
app.include_router(outreach_router)
app.include_router(vms_router)
app.include_router(vettedcare_router)

ADMIN_STATIC_DIR = Path(__file__).resolve().parent / "static" / "admin"
if ADMIN_STATIC_DIR.is_dir():
    app.mount("/admin", StaticFiles(directory=ADMIN_STATIC_DIR, html=True), name="admin")

PORTAL_STATIC_DIR = Path(__file__).resolve().parent / "static" / "portal"
if PORTAL_STATIC_DIR.is_dir():
    app.mount("/portal", StaticFiles(directory=PORTAL_STATIC_DIR, html=True), name="portal")

LANDING_STATIC_DIR = Path(__file__).resolve().parent / "static" / "landing"
if LANDING_STATIC_DIR.is_dir():
    app.mount("/join", StaticFiles(directory=LANDING_STATIC_DIR, html=True), name="join")

register_asgi_app(app)


@app.get("/")
def read_root():
    from app.config import settings

    return {
        "status": "VettedCare.ai Engine Online",
        "product": settings.PROJECT_NAME,
        "tagline": settings.VETTED_TAGLINE,
        "safety_first": True,
        "region": grid_region_label(),
        "admin": "/admin",
        "manus": {
            "config": "/api/vettedcare/manus/config",
            "work_queue": "/api/vettedcare/manus/work-queue",
            "submit_run": "/api/vettedcare/manus/run",
        },
    }


@app.get("/health/vettedcare")
def health_vettedcare(db: Session = Depends(get_db)):
    payload = build_vettedcare_infrastructure_readiness(db)
    return {
        "status": payload["overall"],
        "product": payload["product"],
        "summary": payload["summary"],
        "required_pass": payload["required_pass"],
        "required_total": payload["required_total"],
        "manus_worker_required": False,
        "manus_hook_ready": payload["manus_hook_ready"],
        "checks": payload["checks"],
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
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
    go_live_record = build_production_go_live_record(db)
    launch_attestation = build_production_launch_attestation(db)
    perfection_seal = build_production_launch_perfection_seal(db)
    launch_archive = build_production_launch_archive(db)
    launch_finale = build_production_launch_finale(db)
    bundle_verification = build_production_launch_perfection_manifest(db)
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
        "production_go_live_record_ready": go_live_record["production_go_live_record_ready"],
        "production_launch_attestation_ready": launch_attestation["production_launch_attestation_ready"],
        "production_launch_perfection_ready": perfection_seal["production_launch_perfection_ready"],
        "production_launch_archive_ready": launch_archive["production_launch_archive_ready"],
        "production_launch_finale_ready": launch_finale["production_launch_finale_ready"],
        "production_launch_bundle_verified_ready": bundle_verification[
            "production_launch_bundle_verified_ready"
        ],
    }
