"""In-process mock adapter routes for local live-scraper go-live."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.live_scraper_mock_data import (
    mock_job_board_payload,
    mock_judiciary_search_payload,
    mock_mbon_verify_payload,
    mock_oig_search_payload,
    mock_vms_shifts_payload,
)

router = APIRouter(prefix="/api/adapters", tags=["live-scraper-adapters"])


def _require_mock_adapters() -> None:
    if not settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED:
        raise HTTPException(status_code=404, detail="mock_adapters_disabled")


@router.get("/health")
def mock_adapters_health():
    _require_mock_adapters()
    return {"status": "ok", "mode": "mock_adapter"}


@router.get("/mbon/verify")
def mock_mbon_verify(license: str, name: str = ""):
    _require_mock_adapters()
    return mock_mbon_verify_payload(license_number=str(license or "").strip().upper())


@router.post("/oig/leie/search")
def mock_oig_search(payload: dict):
    _require_mock_adapters()
    return mock_oig_search_payload(full_name=str(payload.get("name") or ""))


@router.get("/md/judiciary/search")
def mock_judiciary_search(name: str):
    _require_mock_adapters()
    return mock_judiciary_search_payload(full_name=str(name or ""))


@router.get("/job-board/crisis")
def mock_job_board_crisis(state: str = "MD", roles: str = "", sources: str = ""):
    _require_mock_adapters()
    return mock_job_board_payload()


@router.get("/vms/shifts")
def mock_vms_shifts():
    _require_mock_adapters()
    return mock_vms_shifts_payload()
