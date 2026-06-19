from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    ExpansionScrapeResponse,
    FacilityScrapePreviewResponse,
    FacilityScrapeRequest,
    FacilityScrapeResponse,
    PostAcuteExpansionScrapeResponse,
)
from app.services.cms_post_acute_scraper import (
    preview_home_health_agencies,
    preview_nursing_homes,
    scrape_and_ingest_home_health_agencies,
    scrape_and_ingest_nursing_homes,
)
from app.services.de_facility_scraper import preview_delaware_hospitals, scrape_and_ingest_delaware_hospitals
from app.services.facility_scrape_expansion import scrape_and_ingest_expansion_states
from app.services.maryland_facility_scraper import (
    preview_maryland_hospitals,
    scrape_and_ingest_maryland_hospitals,
)
from app.services.nj_facility_scraper import preview_new_jersey_hospitals, scrape_and_ingest_new_jersey_hospitals
from app.services.pa_facility_scraper import preview_pennsylvania_hospitals, scrape_and_ingest_pennsylvania_hospitals
from app.services.post_acute_scrape_expansion import scrape_and_ingest_post_acute_mid_atlantic
from app.services.states import normalize_state

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


@router.get(
    "/maryland-hospitals/preview",
    response_model=FacilityScrapePreviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def preview_maryland_hospital_scrape(
    limit: int | None = None,
    county: str | None = None,
):
    try:
        return preview_maryland_hospitals(limit=limit, county=county)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post("/maryland-hospitals", response_model=FacilityScrapeResponse, dependencies=[Depends(require_admin_api_key)])
def ingest_maryland_hospital_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        return scrape_and_ingest_maryland_hospitals(
            db,
            limit=payload.limit,
            county=payload.county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.get(
    "/pennsylvania-hospitals/preview",
    response_model=FacilityScrapePreviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def preview_pennsylvania_hospital_scrape(
    limit: int | None = None,
    county: str | None = None,
):
    try:
        return preview_pennsylvania_hospitals(limit=limit, county=county)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/pennsylvania-hospitals",
    response_model=FacilityScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_pennsylvania_hospital_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        return scrape_and_ingest_pennsylvania_hospitals(
            db,
            limit=payload.limit,
            county=payload.county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.get(
    "/delaware-hospitals/preview",
    response_model=FacilityScrapePreviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def preview_delaware_hospital_scrape(
    limit: int | None = None,
    county: str | None = None,
):
    try:
        return preview_delaware_hospitals(limit=limit, county=county)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/delaware-hospitals",
    response_model=FacilityScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_delaware_hospital_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        return scrape_and_ingest_delaware_hospitals(
            db,
            limit=payload.limit,
            county=payload.county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.get(
    "/new-jersey-hospitals/preview",
    response_model=FacilityScrapePreviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def preview_new_jersey_hospital_scrape(
    limit: int | None = None,
    county: str | None = None,
):
    try:
        return preview_new_jersey_hospitals(limit=limit, county=county)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/new-jersey-hospitals",
    response_model=FacilityScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_new_jersey_hospital_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        return scrape_and_ingest_new_jersey_hospitals(
            db,
            limit=payload.limit,
            county=payload.county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/expansion-states",
    response_model=ExpansionScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_expansion_state_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        result = scrape_and_ingest_expansion_states(
            db,
            limit=payload.limit,
            county=payload.county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc
    return ExpansionScrapeResponse(
        fetched=result.fetched,
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
        pennsylvania=result.pennsylvania,
        delaware=result.delaware,
        new_jersey=result.new_jersey,
    )


@router.get(
    "/nursing-homes/preview",
    response_model=FacilityScrapePreviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def preview_nursing_home_scrape(
    state: str = "MD",
    limit: int | None = None,
    county: str | None = None,
):
    try:
        return preview_nursing_homes(
            normalize_state(state),
            limit=limit,
            county=county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/nursing-homes",
    response_model=FacilityScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_nursing_home_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        return scrape_and_ingest_nursing_homes(
            db,
            normalize_state(payload.state or "MD"),
            limit=payload.limit,
            county=payload.county,
            auto_create_shifts=payload.auto_create_shifts,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.get(
    "/home-health-agencies/preview",
    response_model=FacilityScrapePreviewResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def preview_home_health_scrape(
    state: str = "MD",
    limit: int | None = None,
    county: str | None = None,
):
    try:
        return preview_home_health_agencies(
            normalize_state(state),
            limit=limit,
            county=county,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/home-health-agencies",
    response_model=FacilityScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_home_health_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        return scrape_and_ingest_home_health_agencies(
            db,
            normalize_state(payload.state or "MD"),
            limit=payload.limit,
            county=payload.county,
            auto_create_shifts=payload.auto_create_shifts,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc


@router.post(
    "/post-acute-mid-atlantic",
    response_model=PostAcuteExpansionScrapeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def ingest_post_acute_mid_atlantic_scrape(
    payload: FacilityScrapeRequest,
    db: Session = Depends(get_db),
):
    try:
        result = scrape_and_ingest_post_acute_mid_atlantic(
            db,
            limit=payload.limit,
            county=payload.county,
            auto_create_shifts=payload.auto_create_shifts,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scrape_failed: {exc}") from exc
    return PostAcuteExpansionScrapeResponse(
        fetched=result.fetched,
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
        shifts_facilities_processed=result.shifts_facilities_processed,
        shifts_created=result.shifts_created,
        matched_push_alerts_sent=result.matched_push_alerts_sent,
        nursing_homes=result.nursing_homes,
        home_health=result.home_health,
    )
