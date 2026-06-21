from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_clinician, require_admin_api_key
from app.config import settings
from app.database import get_db
from app.models import MarylandProvider
from app.schemas import (
    ClinicianApplicationStatusResponse,
    ClinicianApplyResponse,
    ClinicianLoginRequest,
    ClinicianLoginResponse,
    ClinicianPlacementOut,
    ClinicianPreferencesOut,
    ClinicianPreferencesUpdateRequest,
    ClinicianVerifyRequest,
    ClinicianVerifyResponse,
    LicenseVerificationLogRead,
    MatchedShiftOut,
    ProviderRead,
    PushConfigResponse,
    PushSubscriptionOut,
    PushSubscriptionRegisterRequest,
    ShiftLockResponse,
)
from app.services.clinician_auth import authenticate_clinician, get_clinician_application_status
from app.services.clinician_preferences import clinician_preferences_snapshot, update_clinician_preferences
from app.services.license_verification import (
    list_pending_clinicians,
    list_verification_history,
    verify_clinician,
)
from app.services.push_alerts import effective_vapid_public_key
from app.services.push_subscriptions import (
    list_push_subscriptions_for_provider,
    register_push_subscription,
    unregister_push_subscription,
)
from app.services.shift_calendar import placement_calendar_filename, placements_to_ics
from app.services.shift_matching import list_matched_shifts_for_provider
from app.services.shift_lock import lock_shift_for_provider
from app.services.vms_submission import list_clinician_placements

router = APIRouter(prefix="/api/clinicians", tags=["clinicians"])


@router.post("/apply", response_model=ClinicianApplyResponse)
def clinician_apply(db: Session = Depends(get_db)):
    _ = db
    raise HTTPException(
        status_code=410,
        detail="use_join_landing",
        headers={"X-Apply-Url": "/join"},
    )


@router.post("/login", response_model=ClinicianLoginResponse)
def clinician_login(payload: ClinicianLoginRequest, db: Session = Depends(get_db)):
    try:
        provider = authenticate_clinician(db, email=str(payload.email), password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid_credentials") from exc
    return ClinicianLoginResponse(
        access_token=create_access_token(provider.provider_id),
        provider=ProviderRead.model_validate(provider),
    )


@router.get("/me", response_model=ProviderRead)
def clinician_me(current: MarylandProvider = Depends(get_current_clinician)):
    return current


@router.get("/me/application", response_model=ClinicianApplicationStatusResponse)
def clinician_application_status(
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    try:
        status = get_clinician_application_status(db, current.provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ClinicianApplicationStatusResponse(
        provider=ProviderRead.model_validate(status["provider"]),
        portal_enabled=status["portal_enabled"],
        verification_history=[
            LicenseVerificationLogRead.model_validate(row) for row in status["verification_history"]
        ],
    )


@router.get("/me/placements", response_model=list[ClinicianPlacementOut])
def clinician_placements(
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    rows = list_clinician_placements(db, current.provider_id)
    return [ClinicianPlacementOut.model_validate(row) for row in rows]


@router.get("/me/preferences", response_model=ClinicianPreferencesOut)
def clinician_preferences(current: MarylandProvider = Depends(get_current_clinician)):
    snapshot = clinician_preferences_snapshot(current)
    return ClinicianPreferencesOut.model_validate(snapshot)


@router.patch("/me/preferences", response_model=ClinicianPreferencesOut)
def clinician_update_preferences(
    payload: ClinicianPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    try:
        provider = update_clinician_preferences(
            db,
            current.provider_id,
            min_hourly_rate=payload.min_hourly_rate,
            service_lines=payload.service_lines,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"provider_not_found", "no_preference_fields"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        if detail in {"service_lines_required", "invalid_service_lines"}:
            raise HTTPException(status_code=422, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    snapshot = clinician_preferences_snapshot(provider)
    return ClinicianPreferencesOut.model_validate(snapshot)


@router.get("/me/matched-shifts", response_model=list[MatchedShiftOut])
def clinician_matched_shifts(
    limit: int = 50,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    rows = list_matched_shifts_for_provider(
        db,
        current,
        limit=limit,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    return [MatchedShiftOut.model_validate(row) for row in rows]


@router.get("/me/matched-shifts/calendar.ics")
def clinician_matched_shifts_calendar(
    limit: int = 50,
    county: str | None = None,
    facility_type: str | None = None,
    shift_role: str | None = None,
    min_pay: float | None = None,
    starts_after: datetime | None = None,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    from app.services.shift_calendar import open_shifts_calendar_filename, open_shifts_to_ics

    rows = list_matched_shifts_for_provider(
        db,
        current,
        limit=limit,
        county=county,
        facility_type=facility_type,
        shift_role=shift_role,
        min_pay=min_pay,
        starts_after=starts_after,
    )
    content = open_shifts_to_ics(rows)
    filename = open_shifts_calendar_filename(prefix="offercare-matched-shifts")
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/me/matched-shifts/{offer_id}/lock", response_model=ShiftLockResponse)
def clinician_lock_matched_shift(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    result = lock_shift_for_provider(db, provider=current, offer_id=offer_id)
    if result.status == "locked":
        return ShiftLockResponse(
            status=result.status,
            message=result.message,
            offer_id=result.offer_id,
            provider_id=result.provider_id,
            placement_id=result.placement_id,
        )
    if result.status == "rejected":
        raise HTTPException(status_code=403, detail=result.status) from None
    if result.status in {"not_matched", "not_found"}:
        raise HTTPException(status_code=404, detail=result.status) from None
    if result.status == "already_locked":
        raise HTTPException(status_code=409, detail=result.status) from None
    raise HTTPException(status_code=400, detail=result.status) from None


@router.get("/me/calendar.ics")
def clinician_placement_calendar(
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    rows = list_clinician_placements(db, current.provider_id, limit=100)
    content = placements_to_ics(rows)
    filename = placement_calendar_filename(current.provider_id)
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/me/push/config", response_model=PushConfigResponse)
def clinician_push_config():
    return PushConfigResponse(
        enabled=settings.PUSH_ALERTS_ENABLED,
        dry_run=settings.PUSH_DRY_RUN,
        public_key=effective_vapid_public_key(),
    )


@router.get("/me/push/subscriptions", response_model=list[PushSubscriptionOut])
def clinician_push_subscriptions(
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    rows = list_push_subscriptions_for_provider(db, current.provider_id)
    return [PushSubscriptionOut.model_validate(row) for row in rows]


@router.post("/me/push/subscribe", response_model=PushSubscriptionOut)
def clinician_push_subscribe(
    payload: PushSubscriptionRegisterRequest,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    try:
        row = register_push_subscription(
            db,
            current.provider_id,
            endpoint=payload.endpoint,
            p256dh_key=payload.keys.p256dh,
            auth_key=payload.keys.auth,
            user_agent=payload.user_agent,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "endpoint_owned_by_other_provider":
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return PushSubscriptionOut.model_validate(row)


@router.delete("/me/push/subscribe")
def clinician_push_unsubscribe(
    payload: PushSubscriptionRegisterRequest,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    removed = unregister_push_subscription(db, current.provider_id, endpoint=payload.endpoint)
    if not removed:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    return {"status": "removed"}


@router.get("/pending", response_model=list[ProviderRead], dependencies=[Depends(require_admin_api_key)])
def pending_clinicians(db: Session = Depends(get_db)):
    return list_pending_clinicians(db)


@router.post("/{provider_id}/verify", response_model=ClinicianVerifyResponse, dependencies=[Depends(require_admin_api_key)])
def clinician_verify(
    provider_id: UUID,
    payload: ClinicianVerifyRequest,
    db: Session = Depends(get_db),
):
    try:
        provider, log = verify_clinician(
            db,
            provider_id,
            action=payload.action,
            notes=payload.notes,
            reviewer=payload.reviewer,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "provider_not_found":
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail == "already_verified":
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return ClinicianVerifyResponse(
        provider=ProviderRead.model_validate(provider),
        log=LicenseVerificationLogRead.model_validate(log),
    )


@router.get(
    "/{provider_id}/verification-history",
    response_model=list[LicenseVerificationLogRead],
    dependencies=[Depends(require_admin_api_key)],
)
def clinician_verification_history(provider_id: UUID, db: Session = Depends(get_db)):
    history = list_verification_history(db, provider_id)
    if not history:
        exists = (
            db.query(MarylandProvider)
            .filter(MarylandProvider.provider_id == provider_id)
            .first()
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
    return history
