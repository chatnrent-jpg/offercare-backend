"""Live scraper / verification channel registry — dry-run vs production readiness."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.services.live_scraper_urls import effective_live_scraper_url, live_scraper_channel_configured


@dataclass(frozen=True)
class LiveScraperChannel:
    id: str
    name: str
    dry_run: bool
    configured: bool
    live_ready: bool
    detail: str
    config_hint: str | None = None
    endpoint: str | None = None


def _channel(
    *,
    id: str,
    name: str,
    dry_run: bool,
    configured: bool,
    live_ready: bool,
    detail: str,
    config_hint: str | None = None,
    endpoint: str | None = None,
) -> LiveScraperChannel:
    return LiveScraperChannel(
        id=id,
        name=name,
        dry_run=dry_run,
        configured=configured,
        live_ready=live_ready,
        detail=detail,
        config_hint=config_hint,
        endpoint=endpoint,
    )


def get_mbon_scraper_status() -> LiveScraperChannel:
    dry_run = settings.MBON_VERIFY_DRY_RUN
    url = effective_live_scraper_url("mbon")
    configured = live_scraper_channel_configured("mbon", dry_run=dry_run)
    live_ready = configured and not dry_run
    if dry_run:
        detail = "MBON license verification uses deterministic dry-run responses."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or MBON_VERIFY_URL, then MBON_VERIFY_DRY_RUN=false."
    elif not url:
        detail = "MBON adapter URL is missing — cannot verify licenses live."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or MBON_VERIFY_URL for live MBON verification."
    else:
        detail = f"Live MBON verification enabled → {url}"
        hint = None
    return _channel(
        id="mbon",
        name="MBON license verify",
        dry_run=dry_run,
        configured=configured,
        live_ready=live_ready,
        detail=detail,
        config_hint=hint,
        endpoint=url or None,
    )


def get_oig_scraper_status() -> LiveScraperChannel:
    dry_run = settings.OIG_SCREEN_DRY_RUN
    url = effective_live_scraper_url("oig")
    configured = live_scraper_channel_configured("oig", dry_run=dry_run)
    live_ready = configured and not dry_run
    if dry_run:
        detail = "OIG LEIE exclusion screening uses dry-run pattern matching."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or OIG_LEIE_SEARCH_URL, then OIG_SCREEN_DRY_RUN=false."
    elif not url:
        detail = "OIG adapter URL is missing — cannot screen exclusions live."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or OIG_LEIE_SEARCH_URL for live OIG screening."
    else:
        detail = f"Live OIG screening enabled → {url}"
        hint = None
    return _channel(
        id="oig",
        name="OIG LEIE screen",
        dry_run=dry_run,
        configured=configured,
        live_ready=live_ready,
        detail=detail,
        config_hint=hint,
        endpoint=url or None,
    )


def get_judiciary_scraper_status() -> LiveScraperChannel:
    dry_run = settings.MD_JUDICIARY_DRY_RUN
    url = effective_live_scraper_url("judiciary")
    configured = live_scraper_channel_configured("judiciary", dry_run=dry_run)
    live_ready = configured and not dry_run
    if dry_run:
        detail = "Maryland judiciary background screen uses dry-run heuristics."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or MD_JUDICIARY_SEARCH_URL, then MD_JUDICIARY_DRY_RUN=false."
    elif not url:
        detail = "Judiciary adapter URL is missing — cannot run judiciary screen live."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or MD_JUDICIARY_SEARCH_URL for live judiciary checks."
    else:
        detail = f"Live judiciary screening enabled → {url}"
        hint = None
    return _channel(
        id="judiciary",
        name="MD judiciary screen",
        dry_run=dry_run,
        configured=configured,
        live_ready=live_ready,
        detail=detail,
        config_hint=hint,
        endpoint=url or None,
    )


def get_job_board_scraper_status() -> LiveScraperChannel:
    dry_run = settings.JOB_BOARD_SCRAPE_DRY_RUN
    url = effective_live_scraper_url("job_board")
    configured = live_scraper_channel_configured("job_board", dry_run=dry_run)
    live_ready = configured and not dry_run
    if dry_run:
        detail = "Indeed / ZipRecruiter crisis scraper returns seeded Maryland listings."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or JOB_BOARD_SCRAPE_URL, then JOB_BOARD_SCRAPE_DRY_RUN=false."
    elif not url:
        detail = "Job board adapter URL is missing — cannot scrape job boards live."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL or JOB_BOARD_SCRAPE_URL for live job board ingest."
    else:
        detail = f"Live job board scraper enabled → {url}"
        hint = None
    return _channel(
        id="job_board",
        name="Job board crisis",
        dry_run=dry_run,
        configured=configured,
        live_ready=live_ready,
        detail=detail,
        config_hint=hint,
        endpoint=url or None,
    )


def get_vms_ingest_scraper_status() -> LiveScraperChannel:
    dry_run = settings.VMS_INGEST_DRY_RUN
    http_url = effective_live_scraper_url("vms_ingest")
    portal_url = str(settings.VMS_INGEST_PORTAL_URL or "").strip()
    playwright = settings.VMS_INGEST_PLAYWRIGHT_ENABLED
    portal_creds = bool(
        str(settings.VMS_INGEST_PORTAL_USER or "").strip()
        and str(settings.VMS_INGEST_PORTAL_PASSWORD or "").strip()
    )
    configured = live_scraper_channel_configured("vms_ingest", dry_run=dry_run)
    live_ready = configured and not dry_run

    if dry_run:
        detail = "VMS shift ingest returns ShiftWise / Fieldglass dry-run portal shifts."
        hint = (
            "Set LIVE_SCRAPER_GATEWAY_BASE_URL or VMS_INGEST_URL (HTTP), or enable Playwright portal creds, "
            "then VMS_INGEST_DRY_RUN=false."
        )
    elif playwright:
        if portal_url and portal_creds:
            detail = f"Live VMS Playwright ingest enabled → {portal_url}"
            hint = None
        else:
            detail = "Playwright VMS ingest enabled but portal URL or credentials are incomplete."
            hint = "Set VMS_INGEST_PORTAL_URL, VMS_INGEST_PORTAL_USER, and VMS_INGEST_PORTAL_PASSWORD."
            live_ready = False
    elif http_url:
        detail = f"Live VMS HTTP ingest enabled → {http_url}"
        hint = None
    else:
        detail = "VMS ingest is live mode but no HTTP URL or Playwright portal is configured."
        hint = "Set LIVE_SCRAPER_GATEWAY_BASE_URL, VMS_INGEST_URL, or enable Playwright portal ingestion."
        live_ready = False

    return _channel(
        id="vms_ingest",
        name="VMS shift ingest",
        dry_run=dry_run,
        configured=configured,
        live_ready=live_ready,
        detail=detail,
        config_hint=hint,
        endpoint=http_url or portal_url or None,
    )


def live_scraper_channels() -> tuple[LiveScraperChannel, ...]:
    return (
        get_mbon_scraper_status(),
        get_oig_scraper_status(),
        get_judiciary_scraper_status(),
        get_job_board_scraper_status(),
        get_vms_ingest_scraper_status(),
    )


def live_scraper_snapshot() -> dict[str, dict]:
    return {
        channel.id: {
            "name": channel.name,
            "dry_run": channel.dry_run,
            "configured": channel.configured,
            "live_ready": channel.live_ready,
            "detail": channel.detail,
            "config_hint": channel.config_hint,
            "endpoint": channel.endpoint,
        }
        for channel in live_scraper_channels()
    }


def live_scrapers_summary() -> dict:
    channels = live_scraper_channels()
    live_count = sum(1 for row in channels if row.live_ready)
    dry_count = sum(1 for row in channels if row.dry_run)
    return {
        "total_channels": len(channels),
        "live_ready_count": live_count,
        "dry_run_count": dry_count,
        "all_live": live_count == len(channels),
        "channels": live_scraper_snapshot(),
    }
