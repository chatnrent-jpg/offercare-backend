"""Resolve effective live scraper adapter URLs from explicit settings or gateway base."""

from __future__ import annotations

from app.config import settings

CHANNEL_ADAPTER_PATHS: dict[str, str] = {
    "mbon": "/mbon/verify",
    "oig": "/oig/leie/search",
    "judiciary": "/md/judiciary/search",
    "job_board": "/job-board/crisis",
    "vms_ingest": "/vms/shifts",
}

CHANNEL_EXPLICIT_URL_SETTINGS: dict[str, str] = {
    "mbon": "MBON_VERIFY_URL",
    "oig": "OIG_LEIE_SEARCH_URL",
    "judiciary": "MD_JUDICIARY_SEARCH_URL",
    "job_board": "JOB_BOARD_SCRAPE_URL",
    "vms_ingest": "VMS_INGEST_URL",
}


def live_scraper_gateway_base() -> str:
    return str(settings.LIVE_SCRAPER_GATEWAY_BASE_URL or "").strip().rstrip("/")


def effective_live_scraper_url(channel_id: str) -> str:
    setting_name = CHANNEL_EXPLICIT_URL_SETTINGS.get(channel_id)
    if setting_name:
        explicit = str(getattr(settings, setting_name, "") or "").strip()
        if explicit:
            return explicit

    adapter_path = CHANNEL_ADAPTER_PATHS.get(channel_id)
    base = live_scraper_gateway_base()
    if base and adapter_path:
        return f"{base}{adapter_path}"
    return ""


def live_scraper_channel_configured(channel_id: str, *, dry_run: bool) -> bool:
    if dry_run:
        return True
    if channel_id == "vms_ingest" and settings.VMS_INGEST_PLAYWRIGHT_ENABLED:
        portal_url = str(settings.VMS_INGEST_PORTAL_URL or "").strip()
        portal_creds = bool(
            str(settings.VMS_INGEST_PORTAL_USER or "").strip()
            and str(settings.VMS_INGEST_PORTAL_PASSWORD or "").strip()
        )
        return bool(portal_url and portal_creds)
    return bool(effective_live_scraper_url(channel_id))
