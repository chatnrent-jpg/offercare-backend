from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import PlacementOut, VmsBatchSubmitResponse, VmsIngestLogOut, VmsIngestResponse, VmsIngestShiftOut, VmsSubmitResponse
from app.services.vms_shift_ingestion import list_vms_ingestion_log, run_vms_ingestion
from app.services.vms_submission import list_placements, submit_pending_placements, submit_placement_to_vms

router = APIRouter(prefix="/api/vms", tags=["vms"])


def _to_response(result) -> VmsSubmitResponse:
    return VmsSubmitResponse(
        placement_id=result.placement_id,
        status=result.status,
        mode=result.mode,
        external_ref=result.external_ref,
        message=result.message,
    )


@router.post("/placements/{placement_id}/submit", response_model=VmsSubmitResponse, dependencies=[Depends(require_admin_api_key)])
def submit_placement(placement_id: UUID, db: Session = Depends(get_db)):
    try:
        result = submit_placement_to_vms(db, placement_id)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"placement_not_found", "placement_incomplete"}:
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail == "already_submitted":
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return _to_response(result)


@router.post("/placements/submit-pending", response_model=VmsBatchSubmitResponse, dependencies=[Depends(require_admin_api_key)])
def submit_pending(limit: int = 25, db: Session = Depends(get_db)):
    results = submit_pending_placements(db, limit=limit)
    responses = [_to_response(row) for row in results]
    submitted = sum(1 for row in responses if row.status == "SUBMITTED")
    return VmsBatchSubmitResponse(submitted=submitted, results=responses)


@router.get("/placements", response_model=list[PlacementOut], dependencies=[Depends(require_admin_api_key)])
def get_placements(
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = list_placements(db, status=status, limit=limit)
    return [PlacementOut.model_validate(row) for row in rows]


@router.post("/shifts/ingest", response_model=VmsIngestResponse, dependencies=[Depends(require_admin_api_key)])
def ingest_vms_shifts_endpoint(persist: bool = True, db: Session = Depends(get_db)):
    try:
        result = run_vms_ingestion(db, persist=persist)
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


@router.get("/shifts/ingest/log", response_model=list[VmsIngestLogOut], dependencies=[Depends(require_admin_api_key)])
def vms_ingestion_log(limit: int = 50, db: Session = Depends(get_db)):
    return [VmsIngestLogOut(**row) for row in list_vms_ingestion_log(db, limit=min(limit, 200))]
