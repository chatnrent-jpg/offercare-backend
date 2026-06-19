"""Public Maryland CNA/LPN worker inflow landing API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MarylandLandingApplyRequest, MarylandLandingApplyResponse, MarylandLandingPageResponse
from app.services.maryland_landing import apply_maryland_floor_staff, build_maryland_landing_page

router = APIRouter(prefix="/api/landing", tags=["landing"])


@router.get("/maryland", response_model=MarylandLandingPageResponse)
def maryland_landing_page():
    return MarylandLandingPageResponse(**build_maryland_landing_page())


@router.post("/maryland/apply", response_model=MarylandLandingApplyResponse)
def maryland_landing_apply(payload: MarylandLandingApplyRequest, db: Session = Depends(get_db)):
    try:
        result = apply_maryland_floor_staff(db, payload)
    except ValueError as exc:
        token = str(exc)
        if token == "duplicate_application":
            raise HTTPException(status_code=409, detail="duplicate_application") from exc
        if token == "portal_account_exists":
            raise HTTPException(status_code=409, detail="portal_account_exists") from exc
        if token in {"unsupported_credential", "npi_required_for_credential"}:
            raise HTTPException(status_code=422, detail=token) from exc
        raise
    return MarylandLandingApplyResponse(**result)
