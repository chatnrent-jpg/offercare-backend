from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    CascadeWorkerStatusResponse,
    CascadeWorkerTickResponse,
    CascadeWorkerTickResultOut,
    ComplianceMonitorResponse,
    ComplianceSchedulerStatusResponse,
    JobBoardCrisisScanResponse,
    OpsAuditEventOut,
    OpsMetricsResponse,
    ProductionOpsDashboardResponse,
    ProductionOpsRefreshRequest,
    StaffingSchedulerStatusResponse,
    VmsIngestResponse,
)
from app.services.cascade_worker import cascade_worker_status, run_cascade_worker_tick
from app.services.compliance_scheduler import (
    compliance_scheduler_status,
    run_compliance_monitor_tick,
)
from app.services.production_ops_dashboard import (
    build_production_ops_dashboard,
    build_production_ops_dashboard_json,
    as_production_ops_dashboard_response,
    refresh_production_ops_dashboard,
)
from app.services.staffing_scheduler import (
    run_job_board_worker_tick,
    run_vms_worker_tick,
    staffing_scheduler_status,
)
from app.services.ops_metrics import get_ops_metrics, list_ops_audit_events

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/metrics", response_model=OpsMetricsResponse, dependencies=[Depends(require_admin_api_key)])
def ops_metrics(db: Session = Depends(get_db)):
    return OpsMetricsResponse.model_validate(get_ops_metrics(db))


@router.get("/audit", response_model=list[OpsAuditEventOut], dependencies=[Depends(require_admin_api_key)])
def ops_audit(limit: int = 50, db: Session = Depends(get_db)):
    rows = list_ops_audit_events(db, limit=min(limit, 200))
    return [OpsAuditEventOut.model_validate(row) for row in rows]


@router.get(
    "/cascade-worker/status",
    response_model=CascadeWorkerStatusResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def cascade_worker_status_endpoint():
    status = cascade_worker_status()
    return CascadeWorkerStatusResponse(
        enabled=status.enabled,
        cascade_enabled=status.cascade_enabled,
        interval_seconds=status.interval_seconds,
        timeout_seconds=status.timeout_seconds,
        running=status.running,
    )


@router.post(
    "/cascade-worker/tick",
    response_model=CascadeWorkerTickResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def cascade_worker_manual_tick(db: Session = Depends(get_db)):
    results = run_cascade_worker_tick(db)
    return CascadeWorkerTickResponse(
        advanced=len(results),
        results=[
            CascadeWorkerTickResultOut(
                offer_id=row.cascade.offer_id,
                status=row.status,
                message=row.message,
                phone_number=row.delivery.phone_number if row.delivery else None,
            )
            for row in results
        ],
    )


@router.get(
    "/staffing-scheduler/status",
    response_model=StaffingSchedulerStatusResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def staffing_scheduler_status_endpoint():
    status = staffing_scheduler_status()
    return StaffingSchedulerStatusResponse(
        vms_enabled=status.vms_enabled,
        vms_interval_seconds=status.vms_interval_seconds,
        vms_running=status.vms_running,
        vms_last_run_at=status.vms_last_run_at,
        job_board_enabled=status.job_board_enabled,
        job_board_interval_seconds=status.job_board_interval_seconds,
        job_board_running=status.job_board_running,
        job_board_last_run_at=status.job_board_last_run_at,
    )


@router.post(
    "/staffing-scheduler/vms-tick",
    response_model=VmsIngestResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def staffing_scheduler_vms_tick(db: Session = Depends(get_db)):
    result = run_vms_worker_tick(db)
    if result.get("skipped"):
        return VmsIngestResponse(
            shifts_fetched=0,
            offers_created=0,
            offers_skipped=0,
            shifts=[],
        )
    return VmsIngestResponse(**result)


@router.post(
    "/staffing-scheduler/job-board-tick",
    response_model=JobBoardCrisisScanResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def staffing_scheduler_job_board_tick(db: Session = Depends(get_db)):
    result = run_job_board_worker_tick(db)
    if result.get("skipped"):
        return JobBoardCrisisScanResponse(
            listings_scraped=0,
            listings_upserted=0,
            crisis_listings=0,
            signals_created=0,
            min_days_threshold=0,
        )
    return JobBoardCrisisScanResponse(**result)


@router.get(
    "/compliance-scheduler/status",
    response_model=ComplianceSchedulerStatusResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def compliance_scheduler_status_endpoint():
    status = compliance_scheduler_status()
    return ComplianceSchedulerStatusResponse(
        enabled=status.enabled,
        interval_seconds=status.interval_seconds,
        running=status.running,
        last_run_at=status.last_run_at,
        last_documents_checked=status.last_documents_checked,
        last_suspended_count=status.last_suspended_count,
    )


@router.post(
    "/compliance-scheduler/tick",
    response_model=ComplianceMonitorResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def compliance_scheduler_manual_tick(db: Session = Depends(get_db)):
    result = run_compliance_monitor_tick(db)
    if result.get("skipped"):
        return ComplianceMonitorResponse(
            documents_checked=0,
            expiring_alerts=[],
            suspended_provider_ids=[],
        )
    return ComplianceMonitorResponse(**result)


@router.get(
    "/production-dashboard",
    response_model=ProductionOpsDashboardResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_ops_dashboard(include_probes: bool = False, db: Session = Depends(get_db)):
    snapshot = build_production_ops_dashboard(db, include_probes=include_probes)
    return as_production_ops_dashboard_response(snapshot)


@router.get("/production-dashboard.json", dependencies=[Depends(require_admin_api_key)])
def production_ops_dashboard_json_download(include_probes: bool = False, db: Session = Depends(get_db)):
    payload = build_production_ops_dashboard_json(db, include_probes=include_probes)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-dashboard/refresh",
    response_model=ProductionOpsDashboardResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_ops_dashboard_refresh(
    payload: ProductionOpsRefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    snapshot = refresh_production_ops_dashboard(
        db,
        probe_scrapers=payload.probe_scrapers if payload else True,
        audit_limit=payload.audit_limit if payload else 25,
    )
    return as_production_ops_dashboard_response(snapshot)
