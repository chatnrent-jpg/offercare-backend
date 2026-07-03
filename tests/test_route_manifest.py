from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "app" / "static" / "landing" / "route_manifest.py"


def _load_manifest():
    spec = importlib.util.spec_from_file_location("landing_route_manifest", _MANIFEST_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_landing_slug() -> None:
    manifest = _load_manifest()
    assert manifest.build_landing_slug("baltimore", "cna") == "baltimore-instant-pay-cna"
    assert manifest.build_landing_slug("silver-spring", "lpn") == "silver-spring-instant-pay-lpn"


def test_iter_routes_count() -> None:
    manifest = _load_manifest()
    routes = list(manifest.iter_routes())
    assert len(routes) == 9  # 3 regions × 3 licenses


def test_region_metadata_payload() -> None:
    manifest = _load_manifest()
    route = manifest.resolve_route_parts("bethesda", "gna")
    meta = manifest.region_metadata_payload(route)
    assert meta["region_slug"] == "bethesda"
    assert meta["county"] == "Montgomery"
    assert meta["credential_type"] == "GNA"
    assert meta["landing_slug"] == "bethesda-instant-pay-gna"


def test_localized_api_builds_page(client) -> None:
    body = client.get("/api/landing/instant-pay/silver-spring/lpn").json()
    assert body["slug"] == "silver-spring-instant-pay-lpn"
    assert body["region_slug"] == "silver-spring"
    assert body["license_slug"] == "lpn"
    assert body["region_metadata"]["county"] == "Montgomery"
    assert body["intake_table"] == "caregiver_intake_queue"


def test_localized_text_apply_queues_with_region_metadata(client) -> None:
    from uuid import uuid4

    from app.services.worker_consent import WORKER_CONSENT_VERSION

    suffix = str(uuid4().int % 10000).zfill(4)
    response = client.post(
        "/api/landing/instant-pay/bethesda/cna/text-apply",
        json={
            "phone_number": f"301555{suffix}",
            "full_name": "Route Test",
            "consent_version": WORKER_CONSENT_VERSION,
            "consent_sms_dispatch": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["region_metadata"]["region_slug"] == "bethesda"
    assert body["landing_slug"] == "bethesda-instant-pay-cna"


def test_route_manifest_api(client) -> None:
    body = client.get("/api/landing/routes/manifest").json()
    assert body["route_count"] == 9
    assert body["intake_table"] == "caregiver_intake_queue"
    assert body["url_pattern"] == "{region}-instant-pay-{license}"
