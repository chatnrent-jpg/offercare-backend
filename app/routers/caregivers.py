"""Dual-account caregiver API — MBON profiles with Tier 1 W-2 and Tier 2 1099 routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.models import EMPLOYMENT_TIER_1099, EMPLOYMENT_TIER_W2, MarylandProvider
from app.schemas import (
    Caregiver1099AccountCreateIn,
    Caregiver1099AccountOut,
    CaregiverAccountBundleOut,
    CaregiverEinValidationIn,
    CaregiverLinkProviderIn,
    CaregiverProfileCreateIn,
    CaregiverProfileOut,
    CaregiverProvisionFromProviderIn,
    CaregiverProvisionIn,
    CaregiverW2AccountCreateIn,
    CaregiverW2AccountOut,
)
from app.services.caregiver_accounts import (
    create_1099_contractor_account,
    create_caregiver_profile,
    create_w2_employee_account,
    get_caregiver_account_bundle,
    get_caregiver_profile_by_mbon,
    link_caregiver_profile_to_provider,
    provision_caregiver_from_provider,
    record_ein_validation,
    tokenize_onboarding_pii_if_present,
)

router = APIRouter(prefix="/api/caregivers", tags=["caregivers"])

_NOT_FOUND = {
    "caregiver_profile_not_found",
    "provider_not_found",
    "contractor_account_not_found",
}
_CONFLICT = {
    "caregiver_profile_conflict",
    "w2_account_conflict",
    "contractor_account_conflict",
    "provider_link_conflict",
}
_BAD_REQUEST = {
    "employment_tier_mismatch",
    "mbon_license_mismatch",
    "invalid_employment_tier",
    "invalid_corporate_ein",
    "invalid_ein_validation_status",
    "mbon_license_number_required",
    "maryland_residence_county_required",
    "corporate_legal_name_required",
    "corporate_identity_required",
    "corporate_ein_required",
    "invalid_ssn",
    "invalid_date_of_birth",
    "invalid_stripe_routing_token",
    "caregiver_pii_empty",
    "skyflow_vault_disabled",
}


def _raise_caregiver_error(exc: ValueError) -> None:
    code = str(exc)
    if code in _NOT_FOUND:
        raise HTTPException(status_code=404, detail=code) from exc
    if code in _CONFLICT:
        raise HTTPException(status_code=409, detail=code) from exc
    if code in _BAD_REQUEST:
        raise HTTPException(status_code=400, detail=code) from exc
    raise HTTPException(status_code=400, detail=code) from exc


def _bundle_to_response(bundle: dict) -> CaregiverAccountBundleOut:
    profile = bundle["profile"]
    tier_account = bundle.get("tier_account")
    w2_account = None
    contractor_account = None
    if bundle["employment_tier"] == EMPLOYMENT_TIER_W2 and tier_account is not None:
        w2_account = CaregiverW2AccountOut.model_validate(tier_account)
    elif bundle["employment_tier"] == EMPLOYMENT_TIER_1099 and tier_account is not None:
        contractor_account = Caregiver1099AccountOut.model_validate(tier_account)
    return CaregiverAccountBundleOut(
        profile=CaregiverProfileOut.model_validate(profile),
        employment_tier=bundle["employment_tier"],
        w2_account=w2_account,
        contractor_account=contractor_account,
    )


@router.post(
    "/profiles",
    response_model=CaregiverProfileOut,
    dependencies=[Depends(require_admin_api_key)],
)
def create_profile(payload: CaregiverProfileCreateIn, db: Session = Depends(get_db)):
    try:
        profile = create_caregiver_profile(
            db,
            mbon_license_number=payload.mbon_license_number,
            full_name=payload.full_name,
            employment_tier=payload.employment_tier,
            credential_type=payload.credential_type,
            email=str(payload.email) if payload.email else None,
            phone_number=payload.phone_number,
            provider_id=payload.provider_id,
            account_status=payload.account_status,
        )
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return CaregiverProfileOut.model_validate(profile)


@router.post(
    "/profiles/{caregiver_profile_id}/w2-account",
    response_model=CaregiverW2AccountOut,
    dependencies=[Depends(require_admin_api_key)],
)
def attach_w2_account(
    caregiver_profile_id: UUID,
    payload: CaregiverW2AccountCreateIn,
    db: Session = Depends(get_db),
):
    try:
        account = create_w2_employee_account(
            db,
            caregiver_profile_id,
            maryland_residence_county=payload.maryland_residence_county,
            local_tax_jurisdiction_code=payload.local_tax_jurisdiction_code,
            w4_on_file=payload.w4_on_file,
            payroll_withholding_status=payload.payroll_withholding_status,
            employee_payroll_number=payload.employee_payroll_number,
        )
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return CaregiverW2AccountOut.model_validate(account)


@router.post(
    "/profiles/{caregiver_profile_id}/1099-account",
    response_model=Caregiver1099AccountOut,
    dependencies=[Depends(require_admin_api_key)],
)
def attach_1099_account(
    caregiver_profile_id: UUID,
    payload: Caregiver1099AccountCreateIn,
    db: Session = Depends(get_db),
):
    try:
        account = create_1099_contractor_account(
            db,
            caregiver_profile_id,
            corporate_legal_name=payload.corporate_legal_name,
            corporate_ein=payload.corporate_ein,
            corporate_ein_validation_status=payload.corporate_ein_validation_status,
        )
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return Caregiver1099AccountOut.model_validate(account)


@router.post(
    "/provision",
    response_model=CaregiverAccountBundleOut,
    dependencies=[Depends(require_admin_api_key)],
)
def provision_caregiver(payload: CaregiverProvisionIn, db: Session = Depends(get_db)):
    try:
        pii_tokens = tokenize_onboarding_pii_if_present(
            ssn=payload.ssn,
            date_of_birth=payload.date_of_birth,
            stripe_routing_token=payload.stripe_routing_token,
        )
        profile = create_caregiver_profile(
            db,
            mbon_license_number=payload.mbon_license_number,
            full_name=payload.full_name,
            employment_tier=payload.employment_tier,
            credential_type=payload.credential_type,
            email=str(payload.email) if payload.email else None,
            phone_number=payload.phone_number,
            provider_id=payload.provider_id,
            pii_tokens=pii_tokens,
            commit=False,
        )
        if payload.employment_tier == EMPLOYMENT_TIER_W2:
            create_w2_employee_account(
                db,
                profile.caregiver_profile_id,
                maryland_residence_county=str(payload.maryland_residence_county),
                local_tax_jurisdiction_code=payload.local_tax_jurisdiction_code,
                w4_on_file=payload.w4_on_file,
                pii_tokens=pii_tokens,
                commit=False,
            )
        else:
            create_1099_contractor_account(
                db,
                profile.caregiver_profile_id,
                corporate_legal_name=str(payload.corporate_legal_name),
                corporate_ein=str(payload.corporate_ein),
                commit=False,
            )
        db.commit()
        bundle = get_caregiver_account_bundle(db, profile.caregiver_profile_id)
    except ValueError as exc:
        db.rollback()
        _raise_caregiver_error(exc)
    except RuntimeError as exc:
        db.rollback()
        code = str(exc)
        if code in {"skyflow_vault_disabled", "skyflow_vault_not_configured"}:
            raise HTTPException(status_code=503, detail=code) from exc
        raise HTTPException(status_code=502, detail=code) from exc
    return _bundle_to_response(bundle)


@router.post(
    "/provision-from-provider/{provider_id}",
    response_model=CaregiverAccountBundleOut,
    dependencies=[Depends(require_admin_api_key)],
)
def provision_from_provider(
    provider_id: UUID,
    payload: CaregiverProvisionFromProviderIn,
    db: Session = Depends(get_db),
):
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="provider_not_found")
    try:
        bundle = provision_caregiver_from_provider(
            db,
            provider,
            employment_tier=payload.employment_tier,
            maryland_residence_county=payload.maryland_residence_county,
            local_tax_jurisdiction_code=payload.local_tax_jurisdiction_code,
            corporate_legal_name=payload.corporate_legal_name,
            corporate_ein=payload.corporate_ein,
            ssn=payload.ssn,
            date_of_birth=payload.date_of_birth,
            stripe_routing_token=payload.stripe_routing_token,
        )
    except ValueError as exc:
        _raise_caregiver_error(exc)
    except RuntimeError as exc:
        code = str(exc)
        if code in {"skyflow_vault_disabled", "skyflow_vault_not_configured"}:
            raise HTTPException(status_code=503, detail=code) from exc
        raise HTTPException(status_code=502, detail=code) from exc
    return _bundle_to_response(bundle)


@router.get(
    "/profiles/mbon/{mbon_license_number}",
    response_model=CaregiverAccountBundleOut,
    dependencies=[Depends(require_admin_api_key)],
)
def get_profile_bundle_by_mbon(mbon_license_number: str, db: Session = Depends(get_db)):
    profile = get_caregiver_profile_by_mbon(db, mbon_license_number)
    if profile is None:
        raise HTTPException(status_code=404, detail="caregiver_profile_not_found")
    try:
        bundle = get_caregiver_account_bundle(db, profile.caregiver_profile_id)
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return _bundle_to_response(bundle)


@router.get(
    "/profiles/{caregiver_profile_id}",
    response_model=CaregiverAccountBundleOut,
    dependencies=[Depends(require_admin_api_key)],
)
def get_profile_bundle(caregiver_profile_id: UUID, db: Session = Depends(get_db)):
    try:
        bundle = get_caregiver_account_bundle(db, caregiver_profile_id)
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return _bundle_to_response(bundle)


@router.post(
    "/profiles/{caregiver_profile_id}/link-provider",
    response_model=CaregiverProfileOut,
    dependencies=[Depends(require_admin_api_key)],
)
def link_provider(
    caregiver_profile_id: UUID,
    payload: CaregiverLinkProviderIn,
    db: Session = Depends(get_db),
):
    try:
        profile = link_caregiver_profile_to_provider(
            db,
            caregiver_profile_id,
            payload.provider_id,
        )
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return CaregiverProfileOut.model_validate(profile)


@router.post(
    "/1099-accounts/{contractor_account_id}/ein-validation",
    response_model=Caregiver1099AccountOut,
    dependencies=[Depends(require_admin_api_key)],
)
def update_ein_validation(
    contractor_account_id: UUID,
    payload: CaregiverEinValidationIn,
    db: Session = Depends(get_db),
):
    try:
        account = record_ein_validation(
            db,
            contractor_account_id,
            status=payload.status,
            validation_reference=payload.validation_reference,
        )
    except ValueError as exc:
        _raise_caregiver_error(exc)
    return Caregiver1099AccountOut.model_validate(account)
