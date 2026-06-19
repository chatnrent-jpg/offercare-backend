from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key, get_current_clinician
from app.database import get_db
from app.models import MarylandFacility, MarylandProvider, OfferCareJobOffer
from app.schemas import (
    CareTaxonomyResponse,
    DemoEnvironmentStatusResponse,
    DemoLinksResponse,
    DemoNotifyMatchedResponse,
    DemoNotifyMatchedOfferResponse,
    DemoPortalHintResponse,
    DemoPortalHintCheckResponse,
    DemoPortalAccountsResponse,
    DemoPushSubscriptionsResponse,
    DemoResetResponse,
    DemoResetOfferResponse,
    DemoSetupResponse,
    DemoGatesResponse,
    DemoReadyGateResponse,
    DemoWalkthroughResponse,
    DemoLockSmokeTestResponse,
    FacilityCreate,
    FacilityRead,
    OfferCreate,
    OfferRead,
    MidAtlanticDemoSeedResponse,
    PostAcuteDemoSeedResponse,
    ProviderCreate,
    ProviderRead,
    ShiftTemplateOut,
    StateCredentialsResponse,
    TaxonomyOptionOut,
)
from app.seed import (
    seed_all_hospital_demos,
    seed_all_mid_atlantic_demos,
    seed_all_post_acute_demos,
    seed_dc_nursing_home_demo,
    seed_de_nursing_home_demo,
    seed_hackensack_demo,
    seed_home_health_demo,
    seed_inova_fairfax_demo,
    seed_nj_nursing_home_demo,
    seed_nursing_home_demo,
    seed_pa_nursing_home_demo,
    seed_saint_judes_demo,
    seed_va_nursing_home_demo,
)
from app.services.care_taxonomy import (
    GNA_LICENSE_STATES,
    care_taxonomy_snapshot,
    credential_options_for_state,
)
from app.services.demo_environment import (
    build_demo_environment_status,
    build_demo_links,
    build_demo_export_bundle,
    build_demo_status_csv,
    build_demo_status_json,
    build_demo_gates_summary,
    build_demo_gates_json,
    build_demo_gates_txt,
    build_demo_ready_gate,
    build_demo_walkthrough_script,
    check_demo_hint_for_clinician,
    get_demo_hint_for_offer,
    notify_matched_on_demo_environment,
    notify_matched_on_demo_offer,
    reset_demo_environment,
    reset_demo_offer,
    run_demo_lock_smoke_test,
    run_full_demo_setup,
)
from app.services.demo_portal_accounts import ensure_demo_portal_accounts
from app.services.demo_push_subscriptions import ensure_demo_push_subscriptions
from app.services.shift_schedule import apply_default_shift_schedule
from app.services.states import grid_region_label, normalize_state, supported_states

router = APIRouter(prefix="/api", tags=["core"])


@router.post("/facilities", response_model=FacilityRead, dependencies=[Depends(require_admin_api_key)])
def create_facility(payload: FacilityCreate, db: Session = Depends(get_db)):
    row = MarylandFacility(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/facilities", response_model=list[FacilityRead])
def list_facilities(db: Session = Depends(get_db)):
    return db.query(MarylandFacility).order_by(MarylandFacility.name).all()


@router.post("/providers", response_model=ProviderRead, dependencies=[Depends(require_admin_api_key)])
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    row = MarylandProvider(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/providers", response_model=list[ProviderRead])
def list_providers(db: Session = Depends(get_db)):
    return db.query(MarylandProvider).order_by(MarylandProvider.full_name).all()


@router.post("/offers", response_model=OfferRead, dependencies=[Depends(require_admin_api_key)])
def create_offer(payload: OfferCreate, db: Session = Depends(get_db)):
    facility = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.facility_id == payload.facility_id)
        .first()
    )
    if facility is None:
        raise HTTPException(status_code=404, detail="facility_not_found")
    row = OfferCareJobOffer(**payload.model_dump())
    apply_default_shift_schedule(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/offers/{offer_id}", response_model=OfferRead)
def get_offer(offer_id: UUID, db: Session = Depends(get_db)):
    row = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == offer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    return row


@router.post("/seed/saint-judes", dependencies=[Depends(require_admin_api_key)])
def seed_demo(db: Session = Depends(get_db)):
    return seed_saint_judes_demo(db)


@router.post("/seed/inova-fairfax", dependencies=[Depends(require_admin_api_key)])
def seed_virginia_demo(db: Session = Depends(get_db)):
    return seed_inova_fairfax_demo(db)


@router.post("/seed/hackensack", dependencies=[Depends(require_admin_api_key)])
def seed_new_jersey_demo(db: Session = Depends(get_db)):
    return seed_hackensack_demo(db)


@router.post("/seed/nursing-home", dependencies=[Depends(require_admin_api_key)])
def seed_nursing_home(db: Session = Depends(get_db)):
    return seed_nursing_home_demo(db)


@router.post("/seed/va-nursing-home", dependencies=[Depends(require_admin_api_key)])
def seed_va_nursing_home(db: Session = Depends(get_db)):
    return seed_va_nursing_home_demo(db)


@router.post("/seed/dc-nursing-home", dependencies=[Depends(require_admin_api_key)])
def seed_dc_nursing_home(db: Session = Depends(get_db)):
    return seed_dc_nursing_home_demo(db)


@router.post("/seed/pa-nursing-home", dependencies=[Depends(require_admin_api_key)])
def seed_pa_nursing_home(db: Session = Depends(get_db)):
    return seed_pa_nursing_home_demo(db)


@router.post("/seed/de-nursing-home", dependencies=[Depends(require_admin_api_key)])
def seed_de_nursing_home(db: Session = Depends(get_db)):
    return seed_de_nursing_home_demo(db)


@router.post("/seed/nj-nursing-home", dependencies=[Depends(require_admin_api_key)])
def seed_nj_nursing_home(db: Session = Depends(get_db)):
    return seed_nj_nursing_home_demo(db)


@router.post("/seed/home-health", dependencies=[Depends(require_admin_api_key)])
def seed_home_health(db: Session = Depends(get_db)):
    return seed_home_health_demo(db)


@router.post("/seed/post-acute-demos", response_model=PostAcuteDemoSeedResponse, dependencies=[Depends(require_admin_api_key)])
def seed_post_acute_demos(db: Session = Depends(get_db)):
    payload = seed_all_post_acute_demos(db)
    return PostAcuteDemoSeedResponse.model_validate(payload)


@router.post("/seed/hospital-demos", response_model=PostAcuteDemoSeedResponse, dependencies=[Depends(require_admin_api_key)])
def seed_hospital_demos(db: Session = Depends(get_db)):
    payload = seed_all_hospital_demos(db)
    return PostAcuteDemoSeedResponse.model_validate(payload)


@router.post("/seed/mid-atlantic-demos", response_model=MidAtlanticDemoSeedResponse, dependencies=[Depends(require_admin_api_key)])
def seed_mid_atlantic_demos(db: Session = Depends(get_db)):
    payload = seed_all_mid_atlantic_demos(db)
    return MidAtlanticDemoSeedResponse.model_validate(payload)


@router.get("/portal/demo-hint", response_model=DemoPortalHintResponse)
def portal_demo_hint(offer_id: UUID, db: Session = Depends(get_db)):
    payload = get_demo_hint_for_offer(db, offer_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="demo_hint_not_found")
    return DemoPortalHintResponse.model_validate(payload)


@router.get("/portal/demo-hint/check", response_model=DemoPortalHintCheckResponse)
def portal_demo_hint_check(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current: MarylandProvider = Depends(get_current_clinician),
):
    payload = check_demo_hint_for_clinician(db, offer_id, current)
    if payload is None:
        raise HTTPException(status_code=404, detail="demo_hint_not_found")
    return DemoPortalHintCheckResponse.model_validate(payload)


@router.get("/seed/demo-status", response_model=DemoEnvironmentStatusResponse, dependencies=[Depends(require_admin_api_key)])
def demo_environment_status(db: Session = Depends(get_db)):
    payload = build_demo_environment_status(db)
    return DemoEnvironmentStatusResponse.model_validate(payload)


@router.get("/seed/demo-links", response_model=DemoLinksResponse, dependencies=[Depends(require_admin_api_key)])
def demo_portal_links(db: Session = Depends(get_db)):
    payload = build_demo_links(db)
    return DemoLinksResponse.model_validate(payload)


@router.get("/seed/demo-gates", response_model=DemoGatesResponse, dependencies=[Depends(require_admin_api_key)])
def demo_gates_summary(db: Session = Depends(get_db)):
    payload = build_demo_gates_summary(db)
    return DemoGatesResponse.model_validate(payload)


@router.get("/seed/demo-gates.json", dependencies=[Depends(require_admin_api_key)])
def demo_gates_json_download(db: Session = Depends(get_db)):
    payload = build_demo_gates_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/seed/demo-gates.txt", dependencies=[Depends(require_admin_api_key)])
def demo_gates_txt_download(db: Session = Depends(get_db)):
    payload = build_demo_gates_txt(db)
    return Response(
        content=payload["content"],
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/seed/demo-ready-gate", response_model=DemoReadyGateResponse, dependencies=[Depends(require_admin_api_key)])
def demo_ready_gate(db: Session = Depends(get_db)):
    payload = build_demo_ready_gate(db)
    return DemoReadyGateResponse.model_validate(payload)


@router.get("/seed/demo-walkthrough", response_model=DemoWalkthroughResponse, dependencies=[Depends(require_admin_api_key)])
def demo_walkthrough_script(db: Session = Depends(get_db)):
    payload = build_demo_walkthrough_script(db)
    return DemoWalkthroughResponse.model_validate(payload)


@router.get("/seed/demo-walkthrough.md", dependencies=[Depends(require_admin_api_key)])
def demo_walkthrough_download(db: Session = Depends(get_db)):
    payload = build_demo_walkthrough_script(db)
    filename = payload.get("filename") or "offercare-demo-walkthrough.md"
    return Response(
        content=payload["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/seed/demo-status.json", dependencies=[Depends(require_admin_api_key)])
def demo_status_json_download(db: Session = Depends(get_db)):
    payload = build_demo_status_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/seed/demo-status.csv", dependencies=[Depends(require_admin_api_key)])
def demo_status_csv_download(db: Session = Depends(get_db)):
    payload = build_demo_status_csv(db)
    return Response(
        content=payload["content"],
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/seed/demo-bundle.zip", dependencies=[Depends(require_admin_api_key)])
def demo_export_bundle_download(db: Session = Depends(get_db)):
    payload = build_demo_export_bundle(db)
    return Response(
        content=payload["content"],
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post("/seed/notify-matched-demos", response_model=DemoNotifyMatchedResponse, dependencies=[Depends(require_admin_api_key)])
def notify_matched_demo_shifts(db: Session = Depends(get_db)):
    payload = notify_matched_on_demo_environment(db)
    payload["demo_status"] = build_demo_environment_status(db)
    return DemoNotifyMatchedResponse.model_validate(payload)


@router.post(
    "/seed/demo-notify-matched",
    response_model=DemoNotifyMatchedOfferResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def notify_matched_demo_offer(offer_id: UUID, db: Session = Depends(get_db)):
    payload = notify_matched_on_demo_offer(db, offer_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="demo_offer_not_found")
    payload["demo_status"] = build_demo_environment_status(db)
    return DemoNotifyMatchedOfferResponse.model_validate(payload)


@router.post("/seed/demo-portal-accounts", response_model=DemoPortalAccountsResponse, dependencies=[Depends(require_admin_api_key)])
def seed_demo_portal_accounts(db: Session = Depends(get_db)):
    payload = ensure_demo_portal_accounts(db)
    payload["demo_status"] = build_demo_environment_status(db)
    return DemoPortalAccountsResponse.model_validate(payload)


@router.post("/seed/demo-push-subscriptions", response_model=DemoPushSubscriptionsResponse, dependencies=[Depends(require_admin_api_key)])
def seed_demo_push_subscriptions(db: Session = Depends(get_db)):
    payload = ensure_demo_push_subscriptions(db)
    payload["demo_status"] = build_demo_environment_status(db)
    return DemoPushSubscriptionsResponse.model_validate(payload)


@router.post("/seed/demo-setup", response_model=DemoSetupResponse, dependencies=[Depends(require_admin_api_key)])
def run_demo_setup(notify_matched: bool = True, db: Session = Depends(get_db)):
    payload = run_full_demo_setup(db, notify_matched=notify_matched)
    return DemoSetupResponse.model_validate(payload)


@router.post("/seed/demo-lock-smoke", response_model=DemoLockSmokeTestResponse, dependencies=[Depends(require_admin_api_key)])
def demo_lock_smoke_test(offer_id: UUID | None = None, db: Session = Depends(get_db)):
    payload = run_demo_lock_smoke_test(db, offer_id=offer_id)
    payload["demo_status"] = build_demo_environment_status(db)
    return DemoLockSmokeTestResponse.model_validate(payload)


@router.post("/seed/demo-reset", response_model=DemoResetResponse, dependencies=[Depends(require_admin_api_key)])
def reset_demo(db: Session = Depends(get_db)):
    payload = reset_demo_environment(db)
    payload["status"] = build_demo_environment_status(db)
    return DemoResetResponse.model_validate(payload)


@router.post(
    "/seed/demo-reset-offer",
    response_model=DemoResetOfferResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def reset_demo_offer_endpoint(offer_id: UUID, db: Session = Depends(get_db)):
    payload = reset_demo_offer(db, offer_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="demo_offer_not_found")
    payload["status"] = build_demo_environment_status(db)
    return DemoResetOfferResponse.model_validate(payload)


@router.get("/care/taxonomy", response_model=CareTaxonomyResponse)
def care_taxonomy():
    snapshot = care_taxonomy_snapshot()
    return CareTaxonomyResponse(
        facility_types=[TaxonomyOptionOut(**row) for row in snapshot["facility_types"]],
        credential_types=[TaxonomyOptionOut(**row) for row in snapshot["credential_types"]],
        shift_roles=[TaxonomyOptionOut(**row) for row in snapshot["shift_roles"]],
        shift_templates_by_facility_type={
            facility_type: [ShiftTemplateOut(**row) for row in rows]
            for facility_type, rows in snapshot["shift_templates_by_facility_type"].items()
        },
        state_credential_rules=snapshot["state_credential_rules"],
    )


@router.get("/care/credentials", response_model=StateCredentialsResponse)
def credentials_for_state(state: str = "MD"):
    normalized = normalize_state(state)
    options = credential_options_for_state(normalized)
    return StateCredentialsResponse(
        state=normalized,
        gna_available=normalized in GNA_LICENSE_STATES,
        credentials=[TaxonomyOptionOut(**row) for row in options],
    )


@router.get("/grid/states")
def grid_states():
    return {"states": supported_states(), "region": grid_region_label()}
