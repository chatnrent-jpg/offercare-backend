"""B2B outreach API for Maryland nursing home crisis targets."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    OutreachCampaignResponse,
    OutreachEmailLogOut,
    OutreachEnrichResponse,
    OutreachTargetOut,
)
from app.services.outreach_pipeline import (
    enrich_contacts_for_facility,
    list_outreach_email_log,
    list_outreach_targets,
    run_outreach_campaign,
)

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.get("/targets", response_model=list[OutreachTargetOut], dependencies=[Depends(require_admin_api_key)])
def outreach_targets(limit: int = Query(default=25, ge=1, le=100), db: Session = Depends(get_db)):
    return [OutreachTargetOut(**row) for row in list_outreach_targets(db, limit=limit)]


@router.post(
    "/facilities/{facility_id}/enrich",
    response_model=OutreachEnrichResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def enrich_facility(facility_id: UUID, db: Session = Depends(get_db)):
    try:
        return OutreachEnrichResponse(**enrich_contacts_for_facility(db, facility_id))
    except ValueError as exc:
        if str(exc) == "facility_not_found":
            raise HTTPException(status_code=404, detail="facility_not_found") from exc
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/campaign/run",
    response_model=OutreachCampaignResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def run_campaign(
    limit: int = Query(default=10, ge=1, le=50),
    send: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return OutreachCampaignResponse(**run_outreach_campaign(db, limit=limit, send=send))


@router.get("/emails/log", response_model=list[OutreachEmailLogOut], dependencies=[Depends(require_admin_api_key)])
def outreach_email_log(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return [OutreachEmailLogOut(**row) for row in list_outreach_email_log(db, limit=limit)]
