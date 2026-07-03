from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.workstream_job_bridge import (
    INSTANT_PAY_HEADER,
    W2_STATUS_HEADER,
    build_baltimore_cna_job_post,
    load_workstream_config,
    run_workstream_baltimore_cna_distribution,
)
from app.services.worker_consent import WORKER_CONSENT_VERSION


@pytest.fixture(autouse=True)
def _workstream_webhook_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKSTREAM_WEBHOOK_BEARER_TOKEN", "test-workstream-webhook-token")


def test_build_baltimore_cna_job_post_headers_and_channels() -> None:
    config = load_workstream_config()
    job_post = build_baltimore_cna_job_post(config)
    assert job_post["landing_slug"] == "baltimore-instant-pay-cna"
    assert "indeed" in job_post["distribution"]["channels"]
    assert "ziprecruiter" in job_post["distribution"]["channels"]
    assert job_post["custom_headers"][INSTANT_PAY_HEADER] == "enabled"
    assert "W-2" in job_post["custom_headers"][W2_STATUS_HEADER]
    assert "/baltimore-instant-pay-cna/" in job_post["position"]["apply_url"]
    assert job_post["webhook"]["destination_table"] == "caregiver_intake_queue"


def test_workstream_distribution_dry_run() -> None:
    summary = run_workstream_baltimore_cna_distribution(dry_run=True)
    assert summary["ok"] is True
    assert summary["push"]["dry_run"] is True
    assert INSTANT_PAY_HEADER in summary["push"]["request_headers"]
    assert W2_STATUS_HEADER in summary["push"]["request_headers"]
    assert len(summary["push"]["channel_payloads"]) == 2


def test_workstream_text_apply_webhook_queues_intake(client: TestClient) -> None:
    suffix = str(uuid4().int % 10000).zfill(4)
    phone = f"410555{suffix}"
    response = client.post(
        "/api/v1/webhooks/workstream/text-apply",
        headers={"Authorization": "Bearer test-workstream-webhook-token"},
        json={
            "event": "text_to_apply_reply",
            "global_phone_number": f"+1{phone}",
            "first_name": "Jordan",
            "last_name": "Smith",
            "referer_source": "Indeed",
            "consent_version": WORKER_CONSENT_VERSION,
            "consent_sms_dispatch": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["queue_status"] == "QUEUED"
    assert body["source_channel"] == "Indeed"
    assert body["intake_id"]


def test_workstream_webhook_requires_bearer(client: TestClient) -> None:
    response = client.post(
        "/api/v1/webhooks/workstream/text-apply",
        json={"phone": "4105559999"},
    )
    assert response.status_code == 401
