"""Portal step 28 — post-lock journey handoff pipeline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import PORTAL_BUILD_ID
from app.services.lock_journey_handoff import lock_journey_handoff_steps


def test_lock_journey_handoff_steps_locked_only() -> None:
    steps = lock_journey_handoff_steps(vms_done=False)
    assert steps[0]["label"] == "Locked"
    assert steps[0]["done"] is True
    assert steps[1]["done"] is False


def test_lock_journey_handoff_steps_with_vms() -> None:
    steps = lock_journey_handoff_steps(vms_done=True)
    assert steps[1]["label"] == "VMS confirmed"
    assert steps[1]["done"] is True


def test_portal_step28_assets(client: TestClient) -> None:
    html = client.get("/portal/").text
    js = client.get("/portal/app.js").text
    assert f'data-portal-build="{PORTAL_BUILD_ID}"' in html
    assert "lock-confirm-pipeline" in html
    assert "renderLockHandoffPipeline" in js
