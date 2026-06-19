"""HTTP client for live scraper adapter calls — in-process when mock adapters are enabled."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.live_scraper_mock_data import (
    mock_job_board_payload,
    mock_judiciary_search_payload,
    mock_mbon_verify_payload,
    mock_oig_search_payload,
    mock_vms_shifts_payload,
)
from app.services.live_scraper_urls import CHANNEL_ADAPTER_PATHS, live_scraper_gateway_base


class _InprocessResponse:
    def __init__(self, payload: dict | list, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "inprocess://adapter")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("inprocess adapter error", request=request, response=response)

    def json(self) -> dict | list:
        return self._payload


def _use_inprocess_transport(url: str) -> bool:
    if not settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED:
        return False
    base = live_scraper_gateway_base()
    if not base:
        return False
    normalized = str(url or "").strip().rstrip("/")
    return normalized.startswith(base)


def _inprocess_adapter_response(
    *,
    method: str,
    url: str,
    params: dict | None = None,
    json: dict | None = None,
) -> _InprocessResponse:
    if not settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED:
        raise RuntimeError("mock_adapters_disabled")

    path = urlparse(url).path
    for channel_id, adapter_path in CHANNEL_ADAPTER_PATHS.items():
        if not path.endswith(adapter_path):
            continue
        if channel_id == "mbon":
            payload = mock_mbon_verify_payload(license_number=str((params or {}).get("license") or ""))
        elif channel_id == "oig":
            payload = mock_oig_search_payload(full_name=str((json or {}).get("name") or ""))
        elif channel_id == "judiciary":
            payload = mock_judiciary_search_payload(full_name=str((params or {}).get("name") or ""))
        elif channel_id == "job_board":
            payload = mock_job_board_payload()
        elif channel_id == "vms_ingest":
            payload = mock_vms_shifts_payload()
        else:
            payload = {"status": "ok"}
        return _InprocessResponse(payload)

    raise RuntimeError(f"unknown_inprocess_adapter_path: {path}")


@contextmanager
def live_scraper_http_client(*, timeout: float) -> Iterator[httpx.Client]:
    with httpx.Client(timeout=timeout) as client:
        yield client


def request_live_scraper(
    *,
    method: str,
    url: str,
    timeout: float,
    params: dict | None = None,
    json: dict | None = None,
) -> httpx.Response | _InprocessResponse:
    if _use_inprocess_transport(url):
        return _inprocess_adapter_response(method=method, url=url, params=params, json=json)

    with live_scraper_http_client(timeout=timeout) as client:
        return client.request(method, url, params=params, json=json)
