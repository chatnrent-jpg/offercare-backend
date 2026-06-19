"""Maryland credentialing, COMAR compliance, and geo-matching API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    ComplianceMonitorResponse,
    ComplianceOverviewResponse,
    CredentialingScreenResponse,
    CrisisScanResponse,
    FacilityCrisisSignalOut,
    GeoMatchedProviderOut,
    JobBoardCrisisScanResponse,
    JobBoardListingOut,
    ProviderComplianceStatusResponse,
    VmsIngestResponse,
    VmsIngestShiftOut,
)
from app.services.audit_report import build_provider_audit_packet
from app.services.compliance_monitor import build_provider_compliance_status, run_compliance_monitor
from app.services.compliance_overview import build_compliance_overview
from app.services.credentialing_pipeline import run_full_credentialing_screen
from app.services.crisis_indicator import (
    list_facility_crisis_signals,
    list_job_board_crisis_listings,
    scan_facility_crisis_signals,
    scan_job_board_crisis_leads,
)
from app.services.geo_matching import list_geo_matched_providers_for_offer
from app.services.vms_shift_ingestion import run_vms_ingestion

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get(
    "/overview",
    response_model=ComplianceOverviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def compliance_overview(limit: int = Query(default=100, ge=1, le=200), db: Session = Depends(get_db)):
    return ComplianceOverviewResponse(**build_compliance_overview(db, limit=limit))


@router.post(
    "/providers/{provider_id}/screen",
    response_model=CredentialingScreenResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def screen_provider_credentials(provider_id: UUID, db: Session = Depends(get_db)):
    try:
        result = run_full_credentialing_screen(db, provider_id)
    except ValueError as exc:
        if str(exc) == "provider_not_found":
            raise HTTPException(status_code=404, detail="provider_not_found") from exc
        raise
    return CredentialingScreenResponse(**result)


@router.get(
    "/providers/{provider_id}/status",
    response_model=ProviderComplianceStatusResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def provider_compliance_status(provider_id: UUID, db: Session = Depends(get_db)):
    try:
        status = build_provider_compliance_status(db, provider_id)
    except ValueError as exc:
        if str(exc) == "provider_not_found":
            raise HTTPException(status_code=404, detail="provider_not_found") from exc
        raise
    return ProviderComplianceStatusResponse(**status)


@router.get(
    "/providers/{provider_id}/audit-packet",
    dependencies=[Depends(require_admin_api_key)],
)
def download_provider_audit_packet(provider_id: UUID, db: Session = Depends(get_db)):
    try:
        payload = build_provider_audit_packet(db, provider_id)
    except ValueError as exc:
        if str(exc) == "provider_not_found":
            raise HTTPException(status_code=404, detail="provider_not_found") from exc
        raise
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="offercare-audit-{provider_id}.zip"'},
    )


@router.post(
    "/monitor/run",
    response_model=ComplianceMonitorResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def run_compliance_monitor_endpoint(db: Session = Depends(get_db)):
    return ComplianceMonitorResponse(**run_compliance_monitor(db))


@router.get(
    "/offers/{offer_id}/geo-matches",
    response_model=list[GeoMatchedProviderOut],
    dependencies=[Depends(require_admin_api_key)],
)
def geo_matches_for_offer(
    offer_id: UUID,
    radius_miles: float | None = Query(default=None, gt=0, le=100),
    limit: int = Query(default=5, ge=1, le=25),
    db: Session = Depends(get_db),
):
    try:
        rows = list_geo_matched_providers_for_offer(
            db,
            offer_id,
            radius_miles=radius_miles,
            limit=limit,
        )
    except ValueError as exc:
        if str(exc) in {"offer_not_found", "facility_not_found"}:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise
    return [GeoMatchedProviderOut(**row) for row in rows]


@router.post(
    "/crisis/scan",
    response_model=CrisisScanResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def scan_crisis_signals(db: Session = Depends(get_db)):
    return CrisisScanResponse(**scan_facility_crisis_signals(db))


@router.get(
    "/crisis/signals",
    response_model=list[FacilityCrisisSignalOut],
    dependencies=[Depends(require_admin_api_key)],
)
def list_crisis_signals(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return [FacilityCrisisSignalOut(**row) for row in list_facility_crisis_signals(db, limit=limit)]


@router.post(
    "/crisis/job-boards/scan",
    response_model=JobBoardCrisisScanResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def scan_job_board_crisis(db: Session = Depends(get_db)):
    try:
        return JobBoardCrisisScanResponse(**scan_job_board_crisis_leads(db))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/crisis/job-boards/listings",
    response_model=list[JobBoardListingOut],
    dependencies=[Depends(require_admin_api_key)],
)
def list_job_board_listings(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return [JobBoardListingOut(**row) for row in list_job_board_crisis_listings(db, limit=limit)]


@router.post(
    "/vms/ingest",
    response_model=VmsIngestResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_vms_shifts_endpoint(db: Session = Depends(get_db)):
    try:
        result = run_vms_ingestion(db, persist=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return VmsIngestResponse(
        shifts_fetched=result["shifts_fetched"],
        offers_created=result["offers_created"],
        offers_skipped=result["offers_skipped"],
        skipped_no_facility=result.get("skipped_no_facility", 0),
        created_offer_ids=result.get("created_offer_ids", []),
        shifts=[
            VmsIngestShiftOut(
                external_id=row["external_id"],
                facility_name=row["facility_name"],
                shift_role=row["shift_role"],
                hourly_pay_rate=row["hourly_pay_rate"],
                shift_starts_at=row["shift_starts_at"],
                source=row["source"],
            )
            for row in result["shifts"]
        ],
    )
