"""Connectivity probes for live scraper adapter channels."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.live_scraper_http import request_live_scraper
from app.services.live_scraper_urls import CHANNEL_ADAPTER_PATHS, effective_live_scraper_url


@dataclass(frozen=True)
class LiveScraperProbeResult:
    channel_id: str
    status: str  # LIVE_OK, DRY_RUN, OFFLINE, ERROR
    endpoint: str | None
    latency_ms: int | None
    message: str


def _dry_run_flag(channel_id: str) -> bool:
    return {
        "mbon": settings.MBON_VERIFY_DRY_RUN,
        "oig": settings.OIG_SCREEN_DRY_RUN,
        "judiciary": settings.MD_JUDICIARY_DRY_RUN,
        "job_board": settings.JOB_BOARD_SCRAPE_DRY_RUN,
        "vms_ingest": settings.VMS_INGEST_DRY_RUN,
    }[channel_id]


def _timeout(channel_id: str) -> float:
    return {
        "mbon": settings.MBON_VERIFY_TIMEOUT_SECONDS,
        "oig": settings.OIG_SCREEN_TIMEOUT_SECONDS,
        "judiciary": settings.MD_JUDICIARY_TIMEOUT_SECONDS,
        "job_board": settings.JOB_BOARD_SCRAPE_TIMEOUT_SECONDS,
        "vms_ingest": settings.VMS_INGEST_TIMEOUT_SECONDS,
    }[channel_id]


def probe_live_scraper_channel(channel_id: str) -> LiveScraperProbeResult:
    if channel_id not in CHANNEL_ADAPTER_PATHS:
        return LiveScraperProbeResult(
            channel_id=channel_id,
            status="ERROR",
            endpoint=None,
            latency_ms=None,
            message=f"Unknown channel: {channel_id}",
        )

    if _dry_run_flag(channel_id):
        return LiveScraperProbeResult(
            channel_id=channel_id,
            status="DRY_RUN",
            endpoint=effective_live_scraper_url(channel_id) or None,
            latency_ms=None,
            message="Channel is still in dry-run mode",
        )

    if channel_id == "vms_ingest" and settings.VMS_INGEST_PLAYWRIGHT_ENABLED:
        portal_url = str(settings.VMS_INGEST_PORTAL_URL or "").strip()
        if portal_url:
            return LiveScraperProbeResult(
                channel_id=channel_id,
                status="LIVE_OK",
                endpoint=portal_url,
                latency_ms=None,
                message="Playwright portal ingest configured — HTTP probe skipped",
            )
        return LiveScraperProbeResult(
            channel_id=channel_id,
            status="OFFLINE",
            endpoint=None,
            latency_ms=None,
            message="Playwright enabled but VMS_INGEST_PORTAL_URL is missing",
        )

    endpoint = effective_live_scraper_url(channel_id)
    if not endpoint:
        return LiveScraperProbeResult(
            channel_id=channel_id,
            status="OFFLINE",
            endpoint=None,
            latency_ms=None,
            message="No adapter URL or LIVE_SCRAPER_GATEWAY_BASE_URL configured",
        )

    timeout = _timeout(channel_id)
    started = time.perf_counter()
    try:
        if channel_id == "oig":
            response = request_live_scraper(
                method="POST",
                url=endpoint,
                timeout=timeout,
                json={"name": "Probe Clinician", "npi": "1234567890"},
            )
        elif channel_id == "mbon":
            response = request_live_scraper(
                method="GET",
                url=endpoint,
                timeout=timeout,
                params={"license": "CNA-PROBE", "name": "Probe Clinician"},
            )
        elif channel_id == "judiciary":
            response = request_live_scraper(
                method="GET",
                url=endpoint,
                timeout=timeout,
                params={"name": "Probe Clinician"},
            )
        else:
            response = request_live_scraper(method="GET", url=endpoint, timeout=timeout)
        response.raise_for_status()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LiveScraperProbeResult(
            channel_id=channel_id,
            status="LIVE_OK",
            endpoint=endpoint,
            latency_ms=latency_ms,
            message=f"Adapter responded HTTP {response.status_code}",
        )
    except httpx.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LiveScraperProbeResult(
            channel_id=channel_id,
            status="ERROR",
            endpoint=endpoint,
            latency_ms=latency_ms,
            message=str(exc),
        )


def probe_all_live_scrapers() -> list[LiveScraperProbeResult]:
    return [probe_live_scraper_channel(channel_id) for channel_id in CHANNEL_ADAPTER_PATHS]
