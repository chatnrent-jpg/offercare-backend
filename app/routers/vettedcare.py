"""VettedCare.ai — credential safety API (Manus acts, VettedCare decides)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key, require_manus_api_key
from app.database import get_db
from app.schemas import (
    ManusBatchRunIn,
    ManusBatchRunResponse,
    ManusIntegrationConfigResponse,
    ManusProviderWorkOrderResponse,
    ManusVettingRunIn,
    ManusVettingRunResponse,
    ManusWorkQueueResponse,
    VettedAlertOut,
    VettedAuditEventOut,
    VettedCareDashboardResponse,
    VettedInfrastructureResponse,
    VettedProviderProfileResponse,
    VettedSafetyCycleResponse,
)
from app.services.manus_ingest import ingest_manus_vetting_run, run_manus_batch_and_cycle
from app.services.manus_work_queue import build_manus_integration_config, build_manus_provider_work_order, build_manus_work_queue
from app.services.vetted_infrastructure import build_vettedcare_infrastructure_readiness
from app.services.vetted_alerts import list_recent_alerts
from app.services.vetted_audit import list_vetted_audit
from app.services.vetted_dashboard import build_vettedcare_dashboard
from app.services.vetted_monitor import run_vettedcare_safety_cycle
from app.services.vetted_status import build_provider_vetted_profile, sync_all_vetted_statuses

router = APIRouter(prefix="/api/vettedcare", tags=["vettedcare"])


@router.get(
    "/infrastructure",
    response_model=VettedInfrastructureResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def vettedcare_infrastructure(db: Session = Depends(get_db)):
    return VettedInfrastructureResponse(**build_vettedcare_infrastructure_readiness(db))


@router.get(
    "/dashboard",
    response_model=VettedCareDashboardResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def vettedcare_dashboard(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return build_vettedcare_dashboard(db, provider_limit=limit)


@router.get(
    "/providers/{provider_id}",
    response_model=VettedProviderProfileResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def vetted_provider_profile(provider_id: UUID, db: Session = Depends(get_db)):
    try:
        return VettedProviderProfileResponse(**build_provider_vetted_profile(db, provider_id))
    except ValueError as exc:
        if str(exc) == "provider_not_found":
            raise HTTPException(status_code=404, detail="provider_not_found") from exc
        raise


@router.post(
    "/sync",
    dependencies=[Depends(require_admin_api_key)],
)
def sync_vetted_statuses(db: Session = Depends(get_db)):
    return sync_all_vetted_statuses(db, actor="admin")


@router.post(
    "/monitor/run",
    response_model=VettedSafetyCycleResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def run_vetted_safety_cycle(db: Session = Depends(get_db)):
    return VettedSafetyCycleResponse(**run_vettedcare_safety_cycle(db, actor="admin"))


@router.get(
    "/audit",
    response_model=list[VettedAuditEventOut],
    dependencies=[Depends(require_admin_api_key)],
)
def list_audit_trail(
    provider_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return [VettedAuditEventOut(**row) for row in list_vetted_audit(db, provider_id=provider_id, limit=limit)]


@router.get(
    "/alerts",
    response_model=list[VettedAlertOut],
    dependencies=[Depends(require_admin_api_key)],
)
def list_alerts(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return [VettedAlertOut(**row) for row in list_recent_alerts(db, limit=limit)]


@router.get(
    "/manus/config",
    response_model=ManusIntegrationConfigResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_integration_config():
    return ManusIntegrationConfigResponse(**build_manus_integration_config())


@router.get(
    "/manus/work-queue",
    response_model=ManusWorkQueueResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_work_queue(
    limit: int = Query(default=25, ge=1, le=200),
    queue: str = Query(
        default="due",
        pattern="^(due|blocked|expiring|action_needed|stale_clear|all)$",
    ),
    db: Session = Depends(get_db),
):
    return ManusWorkQueueResponse(**build_manus_work_queue(db, limit=limit, queue=queue))


@router.get(
    "/manus/providers/{provider_id}",
    response_model=ManusProviderWorkOrderResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_provider_work_order(provider_id: UUID, db: Session = Depends(get_db)):
    try:
        return ManusProviderWorkOrderResponse(**build_manus_provider_work_order(db, provider_id))
    except ValueError as exc:
        if str(exc) == "provider_not_found":
            raise HTTPException(status_code=404, detail="provider_not_found") from exc
        raise


@router.post(
    "/manus/run",
    response_model=ManusVettingRunResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_vetting_run(payload: ManusVettingRunIn, db: Session = Depends(get_db)):
    result = ingest_manus_vetting_run(db, payload.model_dump(), actor="manus")
    return ManusVettingRunResponse(**result)


@router.post(
    "/manus/batch",
    response_model=ManusBatchRunResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_batch_runs(payload: ManusBatchRunIn, db: Session = Depends(get_db)):
    runs = [ingest_manus_vetting_run(db, item.model_dump(), actor="manus") for item in payload.runs]
    applied = sum(1 for row in runs if row.get("status") == "APPLIED")
    failed = sum(1 for row in runs if row.get("status") == "FAILED")
    safety_cycle = None
    if payload.run_cycle_after and applied:
        safety_cycle = VettedSafetyCycleResponse(**run_vettedcare_safety_cycle(db, actor="manus_batch"))
    return ManusBatchRunResponse(
        submitted=len(payload.runs),
        applied=applied,
        failed=failed,
        runs=[ManusVettingRunResponse(**row) for row in runs],
        safety_cycle=safety_cycle,
    )
