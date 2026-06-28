"""Portal open-shifts resilience — regression guard for steps 12–15."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_portal_open_shifts_uses_public_endpoint_first(client: TestClient) -> None:
    js = client.get("/portal/app.js").text
    assert 'api(`/api/shifts/open?${baseQuery}`)' in js
    assert "mapBasicOpenShiftRow" in js
    assert "enrichOpenShiftsWithMatched" in js
    assert "API_TIMEOUT_MS" in js
    assert "refreshShiftsTab" in js
    bootstrap_start = js.index("async function bootstrap()")
    bootstrap_end = js.index("els.tabLogin", bootstrap_start)
    bootstrap = js[bootstrap_start:bootstrap_end]
    assert "registerPortalServiceWorker().catch" in bootstrap
    assert "await registerPortalServiceWorker()" not in bootstrap


def test_portal_open_shifts_not_gated_on_missing_me_open_shifts(client: TestClient) -> None:
    """Signed-in load path must work when /me/open-shifts is absent on older API builds."""
    js = client.get("/portal/app.js").text
    start = js.index("async function loadShifts()")
    end = js.index("function populateShiftFilters")
    block = js[start:end]
    assert 'api(`/api/shifts/open?${baseQuery}`)' in block
    assert block.index('api(`/api/shifts/open?${baseQuery}`)') < block.index("enrichOpenShiftsWithMatched")


def test_verify_portal_live_script_checks_open_shifts_path() -> None:
    from pathlib import Path

    text = Path("scripts/verify_portal_live.py").read_text(encoding="utf-8")
    assert "purgeStalePortalCache" in text
    assert "isAuthError" in text


def test_open_shifts_public_endpoint_returns_rows(client: TestClient) -> None:
    response = client.get("/api/shifts/open?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
