"""Public Maryland CNA/LPN worker inflow landing API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    MarylandLandingApplyRequest,
    MarylandLandingApplyResponse,
    MarylandLandingPageResponse,
    WorkerInflowSummaryResponse,
    WorkerPrivacyPolicyResponse,
    WorkerTermsOfServiceResponse,
)
from app.services.maryland_landing import apply_maryland_floor_staff, build_maryland_landing_page
from app.services.worker_consent import build_worker_inflow_summary
from app.services.worker_privacy_policy import build_worker_privacy_policy
from app.services.worker_terms_of_service import build_worker_terms_of_service

router = APIRouter(prefix="/api/landing", tags=["landing"])


@router.get("/maryland", response_model=MarylandLandingPageResponse)
def maryland_landing_page():
    return MarylandLandingPageResponse(**build_maryland_landing_page())


@router.get("/maryland/terms-of-service", response_model=WorkerTermsOfServiceResponse)
def maryland_worker_terms_of_service():
    return WorkerTermsOfServiceResponse(**build_worker_terms_of_service())


@router.get("/maryland/privacy-policy", response_model=WorkerPrivacyPolicyResponse)
def maryland_worker_privacy_policy():
    return WorkerPrivacyPolicyResponse(**build_worker_privacy_policy())


@router.post("/maryland/apply", response_model=MarylandLandingApplyResponse)
def maryland_landing_apply(
    payload: MarylandLandingApplyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else None
    try:
        result = apply_maryland_floor_staff(db, payload, client_ip=client_ip)
    except ValueError as exc:
        token = str(exc)
        if token == "duplicate_application":
            raise HTTPException(status_code=409, detail="duplicate_application") from exc
        if token == "portal_account_exists":
            raise HTTPException(status_code=409, detail="portal_account_exists") from exc
        if token in {
            "unsupported_credential",
            "npi_required_for_credential",
            "consent_required",
            "consent_version_mismatch",
        }:
            raise HTTPException(status_code=422, detail=token) from exc
        raise
    return MarylandLandingApplyResponse(**result)


@router.get(
    "/maryland/inflow-summary",
    response_model=WorkerInflowSummaryResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def maryland_worker_inflow_summary(db: Session = Depends(get_db)):
    return WorkerInflowSummaryResponse(**build_worker_inflow_summary(db))
