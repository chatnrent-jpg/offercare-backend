from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    EmailIntegrationStatus,
    IntegrationsStatusResponse,
    LiveScraperChannelOut,
    LiveScraperGoLiveProfileResponse,
    LiveScraperProbeOut,
    LiveScraperProbeResponse,
    LiveScrapersStatusResponse,
    PushIntegrationStatus,
    TestEmailRequest,
    TestEmailResponse,
    TestPushRequest,
    TestPushResponse,
    TestSmsRequest,
    TestSmsResponse,
    TestVmsResponse,
    TwilioIntegrationStatus,
    TwilioLockReplySmokeRequest,
    TwilioLockReplySmokeResponse,
    TwilioSmsProductionRunbookResponse,
    VmsIntegrationStatus,
)
from app.services.email_alerts import send_shift_email
from app.services.integrations import integration_snapshot
from app.services.live_scraper_go_live import build_live_scraper_go_live_profile
from app.services.live_scraper_probes import probe_all_live_scrapers, probe_live_scraper_channel
from app.services.live_scrapers import live_scraper_snapshot, live_scrapers_summary
from app.services.push_alerts import send_shift_push
from app.services.sms import send_shift_sms
from app.services.twilio_lock_reply_smoke import run_twilio_lock_reply_smoke
from app.services.twilio_sms_production_runbook import build_twilio_sms_production_runbook
from app.services.vms_submission import run_vms_connectivity_test

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/status", response_model=IntegrationsStatusResponse, dependencies=[Depends(require_admin_api_key)])
def integrations_status():
    snapshot = integration_snapshot()
    return IntegrationsStatusResponse(
        twilio=TwilioIntegrationStatus(**snapshot["twilio"]),
        email=EmailIntegrationStatus(**snapshot["email"]),
        vms=VmsIntegrationStatus(**snapshot["vms"]),
        push=PushIntegrationStatus(**snapshot["push"]),
    )


@router.get(
    "/live-scrapers",
    response_model=LiveScrapersStatusResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def live_scrapers_status():
    summary = live_scrapers_summary()
    channels = {
        key: LiveScraperChannelOut(**value)
        for key, value in live_scraper_snapshot().items()
    }
    return LiveScrapersStatusResponse(
        total_channels=summary["total_channels"],
        live_ready_count=summary["live_ready_count"],
        dry_run_count=summary["dry_run_count"],
        all_live=summary["all_live"],
        channels=channels,
    )


@router.get(
    "/live-scrapers/go-live-profile",
    response_model=LiveScraperGoLiveProfileResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def live_scrapers_go_live_profile():
    profile = build_live_scraper_go_live_profile()
    return LiveScraperGoLiveProfileResponse(**profile)


@router.post(
    "/live-scrapers/probe",
    response_model=LiveScraperProbeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def live_scrapers_probe_all():
    probes = probe_all_live_scrapers()
    return LiveScraperProbeResponse(
        probes=[LiveScraperProbeOut(**probe.__dict__) for probe in probes],
    )


@router.post(
    "/live-scrapers/{channel_id}/probe",
    response_model=LiveScraperProbeOut,
    dependencies=[Depends(require_admin_api_key)],
)
def live_scraper_probe(channel_id: str):
    probe = probe_live_scraper_channel(channel_id)
    return LiveScraperProbeOut(**probe.__dict__)


@router.get(
    "/twilio/go-live-profile",
    response_model=TwilioSmsProductionRunbookResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def twilio_sms_go_live_profile(db: Session = Depends(get_db)):
    runbook = build_twilio_sms_production_runbook(db)
    return TwilioSmsProductionRunbookResponse(
        production_ready=runbook["production_ready"],
        live_sms_ready=runbook["live_sms_ready"],
        summary=runbook["summary"],
        checks=runbook["checks"],
        steps=runbook["steps"],
        env_snippet=runbook["env_snippet"],
        twilio_console_steps=runbook["twilio_console_steps"],
    )


@router.post(
    "/twilio/lock-reply-smoke",
    response_model=TwilioLockReplySmokeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def twilio_lock_reply_smoke(
    payload: TwilioLockReplySmokeRequest | None = None,
    db: Session = Depends(get_db),
):
    result = run_twilio_lock_reply_smoke(db, phone_number=payload.phone_number if payload else None)
    return TwilioLockReplySmokeResponse(**result)


@router.post("/test/sms", response_model=TestSmsResponse, dependencies=[Depends(require_admin_api_key)])
def test_sms_delivery(payload: TestSmsRequest):
    result = send_shift_sms(to_number=payload.phone_number, message_body=payload.message)
    return TestSmsResponse(
        status=result.status,
        mode=result.mode,
        twilio_sid=result.twilio_sid,
        error=result.error,
    )


@router.post("/test/email", response_model=TestEmailResponse, dependencies=[Depends(require_admin_api_key)])
def test_email_delivery(payload: TestEmailRequest):
    result = send_shift_email(
        to_address=str(payload.email_address),
        subject=payload.subject,
        message_body=payload.message,
    )
    return TestEmailResponse(
        status=result.status,
        mode=result.mode,
        message_id=result.message_id,
        error=result.error,
    )


@router.post("/test/push", response_model=TestPushResponse, dependencies=[Depends(require_admin_api_key)])
def test_push_delivery(payload: TestPushRequest):
    result = send_shift_push(
        endpoint=payload.endpoint,
        p256dh_key=payload.p256dh_key,
        auth_key=payload.auth_key,
        title=payload.title,
        message_body=payload.message,
    )
    return TestPushResponse(
        status=result.status,
        mode=result.mode,
        receipt_id=result.receipt_id,
        error=result.error,
    )


@router.post("/test/vms", response_model=TestVmsResponse, dependencies=[Depends(require_admin_api_key)])
def test_vms_delivery():
    result = run_vms_connectivity_test()
    return TestVmsResponse(
        status=result["status"],
        mode=result["mode"],
        external_ref=result.get("external_ref"),
        message=result["message"],
    )
