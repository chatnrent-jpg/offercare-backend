"""VettedMe.ai — credential safety API (Manus acts, VettedMe decides)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key, require_manus_api_key
from app.database import get_db
from app.schemas import (
    ManusBatchRunIn,
    ManusBatchRunResponse,
    ManusDeskHandoffResponse,
    ManusDeskBackupCascadeAdvanceIn,
    ManusDeskBackupCascadeAdvanceResponse,
    ManusDeskLiveCalloutIn,
    ManusDeskLiveCalloutResponse,
    ManusDeskPipelineRunIn,
    ManusDeskPipelineRunResponse,
    ManusDeskProductionRunIn,
    ManusIntegrationConfigResponse,
    ManusLeadImportIn,
    ManusProviderWorkOrderResponse,
    ManusRecruitmentConfigResponse,
    ManusRecruitmentProcessResponse,
    ManusShiftIngestIn,
    ManusVettingRunIn,
    ManusVettingRunResponse,
    ManusWorkQueueResponse,
    RecruitmentDashboardResponse,
    VettedAlertOut,
    VettedAuditEventOut,
    VettedMeDashboardResponse,
    VettedInfrastructureResponse,
    VettedProviderProfileResponse,
    VettedSafetyCycleResponse,
)
from app.services.manus_ingest import ingest_manus_vetting_run, run_manus_batch_and_cycle
from app.services.manus_recruitment import build_manus_recruitment_config
from app.services.manus_work_queue import build_manus_integration_config, build_manus_provider_work_order, build_manus_work_queue
from app.services.md_desk_pipeline import (
    build_manus_desk_handoff,
    run_md_desk_pipeline,
    run_md_desk_pipeline_production,
    run_md_desk_production_live_callout,
)
from app.services.recruitment_dashboard import build_recruitment_dashboard
from app.services.vetted_infrastructure import build_vettedme_infrastructure_readiness
from app.services.vetted_alerts import list_recent_alerts
from app.services.vetted_audit import list_vetted_audit
from app.services.vetted_dashboard import build_vettedme_dashboard
from app.services.vetted_monitor import run_vettedme_safety_cycle
from app.services.vetted_status import build_provider_vetted_profile, sync_all_vetted_statuses

router = APIRouter(prefix="/api/vettedme", tags=["vettedme"])


@router.get(
    "/infrastructure",
    response_model=VettedInfrastructureResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def vettedme_infrastructure(db: Session = Depends(get_db)):
    return VettedInfrastructureResponse(**build_vettedme_infrastructure_readiness(db))


@router.get(
    "/dashboard",
    response_model=VettedMeDashboardResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def vettedme_dashboard(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return build_vettedme_dashboard(db, provider_limit=limit)


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
    return VettedSafetyCycleResponse(**run_vettedme_safety_cycle(db, actor="admin"))


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
        safety_cycle = VettedSafetyCycleResponse(**run_vettedme_safety_cycle(db, actor="manus_batch"))
    return ManusBatchRunResponse(
        submitted=len(payload.runs),
        applied=applied,
        failed=failed,
        runs=[ManusVettingRunResponse(**row) for row in runs],
        safety_cycle=safety_cycle,
    )


@router.get(
    "/manus/desk/handoff",
    response_model=ManusDeskHandoffResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_desk_handoff():
    return ManusDeskHandoffResponse(**build_manus_desk_handoff())


@router.post(
    "/manus/desk/run",
    response_model=ManusDeskPipelineRunResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_desk_pipeline_run(payload: ManusDeskPipelineRunIn):
    try:
        result = run_md_desk_pipeline(
            pipeline=payload.pipeline,  # type: ignore[arg-type]
            order_id=payload.order_id,
            evaluation_timestamp=payload.evaluation_timestamp,
            request_timestamp=payload.request_timestamp,
            disrupted_shift_id=payload.disrupted_shift_id,
            original_provider_id=payload.original_provider_id,
            facility_id=payload.facility_id,
            provider_id=payload.provider_id,
            total_hours_worked=payload.total_hours_worked,
            persist=payload.persist,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ManusDeskPipelineRunResponse(**result)


@router.post(
    "/manus/desk/run-production",
    response_model=ManusDeskPipelineRunResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_desk_production_run(payload: ManusDeskProductionRunIn, db: Session = Depends(get_db)):
    try:
        result = run_md_desk_pipeline_production(
            db,
            evaluation_timestamp=payload.evaluation_timestamp,
            request_timestamp=payload.request_timestamp,
            persist=payload.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ManusDeskPipelineRunResponse(**result)


@router.post(
    "/manus/desk/run-production-live",
    response_model=ManusDeskLiveCalloutResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_desk_production_live_callout(payload: ManusDeskLiveCalloutIn, db: Session = Depends(get_db)):
    try:
        result = run_md_desk_production_live_callout(db, original_provider_id=payload.original_provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ManusDeskLiveCalloutResponse(**result)


@router.post(
    "/manus/desk/advance-backup-cascade",
    response_model=ManusDeskBackupCascadeAdvanceResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_desk_advance_backup_cascade(payload: ManusDeskBackupCascadeAdvanceIn, db: Session = Depends(get_db)):
    from app.services.md_backup_notify_cascade import advance_backup_notify_cascade

    try:
        result = advance_backup_notify_cascade(
            db,
            payload.dispatch_id,
            force=payload.force,
            actor="manus_api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ManusDeskBackupCascadeAdvanceResponse(
        ok=True,
        status=result.status,
        message=result.message,
        dispatch_id=result.dispatch_id,
        notification=result.notification,
        cascade=result.cascade,
    )


@router.get(
    "/manus/recruitment/config",
    response_model=ManusRecruitmentConfigResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_recruitment_config():
    return ManusRecruitmentConfigResponse(**build_manus_recruitment_config())


@router.post(
    "/manus/recruitment/leads/import",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_import_leads(payload: ManusLeadImportIn, db: Session = Depends(get_db)):
    from data_engine.lead_schema import import_raw_leads_csv
    from data_engine.paths import RAW_LEADS_DIR, ensure_data_engine_dirs

    ensure_data_engine_dirs()
    csv_path = RAW_LEADS_DIR / payload.csv_filename
    if not csv_path.is_file():
        raise HTTPException(status_code=404, detail="csv_not_found")
    result = import_raw_leads_csv(db, csv_path)
    return ManusRecruitmentProcessResponse(ok=True, detail=result)


@router.post(
    "/manus/recruitment/shifts",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_ingest_shifts(payload: ManusShiftIngestIn, db: Session = Depends(get_db)):
    from data_engine.shift_ingest import ingest_manus_shift_payload

    result = ingest_manus_shift_payload(db, {"shifts": payload.shifts})
    return ManusRecruitmentProcessResponse(ok=True, detail=result)


@router.post(
    "/manus/recruitment/contracts/process",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_process_contracts(db: Session = Depends(get_db)):
    from data_engine.contract_processor import process_incoming_contracts_dir

    results = process_incoming_contracts_dir(db)
    return ManusRecruitmentProcessResponse(ok=True, detail=results)


@router.get(
    "/recruitment/dashboard",
    response_model=RecruitmentDashboardResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_dashboard(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return RecruitmentDashboardResponse(**build_recruitment_dashboard(db, limit=limit))


@router.post(
    "/recruitment/contracts/process",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def admin_process_contracts(db: Session = Depends(get_db)):
    from data_engine.contract_processor import process_incoming_contracts_dir

    return ManusRecruitmentProcessResponse(ok=True, detail=process_incoming_contracts_dir(db))


@router.post(
    "/recruitment/shifts/process-dir",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def admin_process_shift_dropzone(db: Session = Depends(get_db)):
    from data_engine.shift_ingest import ingest_shifts_from_directory

    return ManusRecruitmentProcessResponse(ok=True, detail=ingest_shifts_from_directory(db))


@router.post(
    "/recruitment/leads/import-all",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def admin_import_all_leads(db: Session = Depends(get_db)):
    from data_engine.lead_schema import import_raw_leads_csv
    from data_engine.paths import RAW_LEADS_DIR, ensure_data_engine_dirs

    ensure_data_engine_dirs()
    results = []
    for csv_path in sorted(RAW_LEADS_DIR.glob("*.csv")):
        if csv_path.name == "md_facilities.csv":
            from data_engine.md_lead_schema import import_md_facilities_csv

            results.append(import_md_facilities_csv(db, csv_path))
        else:
            results.append(import_raw_leads_csv(db, csv_path))
    return ManusRecruitmentProcessResponse(ok=True, detail=results)


@router.post(
    "/manus/recruitment/leads/import-md",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_manus_api_key)],
)
def manus_import_md_facilities(
    payload: ManusLeadImportIn,
    db: Session = Depends(get_db),
):
    from data_engine.md_lead_schema import import_md_facilities_csv
    from data_engine.paths import RAW_LEADS_DIR, ensure_data_engine_dirs

    ensure_data_engine_dirs()
    filename = payload.csv_filename or "md_facilities.csv"
    csv_path = RAW_LEADS_DIR / filename
    if not csv_path.is_file():
        raise HTTPException(status_code=404, detail="csv_not_found")
    result = import_md_facilities_csv(db, csv_path)
    return ManusRecruitmentProcessResponse(ok=True, detail=result)


@router.get(
    "/recruitment/md-outreach-queue",
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_md_outreach_queue(db: Session = Depends(get_db)):
    from data_engine.md_outreach_sequencer import export_manus_outreach_queue

    return export_manus_outreach_queue(db)


@router.post(
    "/recruitment/md-outreach/sync-facilities",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_md_outreach_sync_facilities(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    from data_engine.md_outreach_sequencer import sync_ready_facility_contacts_to_outreach

    return ManusRecruitmentProcessResponse(
        ok=True,
        detail=sync_ready_facility_contacts_to_outreach(db, limit=limit),
    )


@router.post(
    "/recruitment/md-outreach-snapshot",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_md_outreach_snapshot(db: Session = Depends(get_db)):
    from data_engine.md_outreach_sequencer import write_manus_outreach_snapshot

    path = write_manus_outreach_snapshot(db)
    return ManusRecruitmentProcessResponse(ok=True, detail={"snapshot_path": str(path)})


@router.post(
    "/recruitment/md-licensure/batch",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_md_licensure_batch(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    from compliance.md_licensure_validator import run_md_licensure_batch

    return ManusRecruitmentProcessResponse(ok=True, detail=run_md_licensure_batch(db, limit=limit))


@router.post(
    "/recruitment/md-facilities/import-scraped",
    response_model=ManusRecruitmentProcessResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_import_md_facilities(db: Session = Depends(get_db)):
    from data_engine.md_facility_import import import_scraped_facilities_csv

    return ManusRecruitmentProcessResponse(ok=True, detail=import_scraped_facilities_csv(db))


@router.get(
    "/recruitment/manus-snapshot",
    dependencies=[Depends(require_admin_api_key)],
)
def recruitment_manus_snapshot(db: Session = Depends(get_db)):
    from app.services.recruitment_dashboard import build_manus_recruitment_snapshot

    return build_manus_recruitment_snapshot(db)
