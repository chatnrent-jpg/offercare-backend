from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    OpenShiftOut,
    ShiftAutoCreateFacilityResult,
    ShiftAutoCreateRequest,
    ShiftAutoCreateResponse,
    ShiftFilterOptionsResponse,
    ShiftScheduleUpdateRequest,
)
from app.services.shift_calendar import open_shifts_calendar_filename, open_shifts_to_ics
from app.services.shift_offer_generator import auto_create_open_shifts, get_open_shift_by_id, get_open_shift_filters, list_open_shifts
from app.services.shift_schedule_editor import update_offer_shift_schedule
from app.services.matched_shift_alerts import notify_matched_clinicians_for_offer

router = APIRouter(prefix="/api/shifts", tags=["shifts"])


@router.post("/auto-create", response_model=ShiftAutoCreateResponse, dependencies=[Depends(require_admin_api_key)])
def auto_create_shifts(payload: ShiftAutoCreateRequest, db: Session = Depends(get_db)):
    results = auto_create_open_shifts(
        db,
        limit=payload.limit,
        state=payload.state,
        county=payload.county,
        icu_rate=payload.icu_rate,
        er_rate=payload.er_rate,
        med_surg_rate=payload.med_surg_rate,
    )
    facility_results = [
        ShiftAutoCreateFacilityResult(
            facility_id=row.facility_id,
            facility_name=row.facility_name,
            created_offers=row.created_offers,
            skipped_roles=row.skipped_roles,
        )
        for row in results
    ]
    offers_created = sum(len(row.created_offers) for row in facility_results)
    created_offer_ids = [offer_id for row in results for offer_id in row.created_offers]
    matched_push_alerts_sent = 0
    if created_offer_ids:
        from app.services.matched_shift_alerts import notify_matched_clinicians_for_offers

        matched_push_alerts_sent = notify_matched_clinicians_for_offers(db, created_offer_ids)
    return ShiftAutoCreateResponse(
        facilities_processed=len(facility_results),
        offers_created=offers_created,
        matched_push_alerts_sent=matched_push_alerts_sent,
        results=facility_results,
    )


@router.post(
    "/offers/{offer_id}/notify-matched",
    dependencies=[Depends(require_admin_api_key)],
)
def notify_matched_shift_alerts(offer_id: UUID, db: Session = Depends(get_db)):
    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    sent = notify_matched_clinicians_for_offer(db, offer_id)
    return {"offer_id": str(offer_id), "matched_push_alerts_sent": sent}


@router.get("/filters", response_model=ShiftFilterOptionsResponse)
def shift_filter_options(db: Session = Depends(get_db)):
    options = get_open_shift_filters(db)
    return ShiftFilterOptionsResponse(**options)


@router.get("/open", response_model=list[OpenShiftOut])
def open_shifts(
    limit: int = 50,
    state: str | None = None,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
    db: Session = Depends(get_db),
):
    rows = list_open_shifts(
        db,
        limit=limit,
        state=state,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    return [OpenShiftOut.model_validate(row) for row in rows]


@router.get("/offers/{offer_id}", response_model=OpenShiftOut, dependencies=[Depends(require_admin_api_key)])
def get_shift_offer(offer_id: UUID, db: Session = Depends(get_db)):
    row = get_open_shift_by_id(db, offer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    return OpenShiftOut.model_validate(row)


@router.patch(
    "/offers/{offer_id}/schedule",
    response_model=OpenShiftOut,
    dependencies=[Depends(require_admin_api_key)],
)
def patch_shift_schedule(
    offer_id: UUID,
    payload: ShiftScheduleUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        row = update_offer_shift_schedule(
            db,
            offer_id,
            shift_starts_at=payload.shift_starts_at,
            shift_ends_at=payload.shift_ends_at,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "offer_not_found":
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail in {"offer_locked", "invalid_schedule_window"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return OpenShiftOut.model_validate(row)


@router.get("/open/calendar.ics")
def open_shifts_calendar(
    limit: int = 50,
    state: str | None = None,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
    db: Session = Depends(get_db),
):
    rows = list_open_shifts(
        db,
        limit=limit,
        state=state,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    content = open_shifts_to_ics(rows)
    filename = open_shifts_calendar_filename()
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
