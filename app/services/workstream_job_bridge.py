"""Workstream API job distribution bridge — Baltimore instant-pay CNA → Indeed & ZipRecruiter."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from app.services.baltimore_instant_pay_landing import LANDING_SLUG, build_baltimore_instant_pay_landing_page
from data_engine.paths import LEADS_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = REPO_ROOT / "integrations" / "workstream" / "baltimore_instant_pay_cna.template.json"
DEFAULT_EXPORT_PATH = LEADS_DIR / "workstream_baltimore_cna_job_posts.json"

INSTANT_PAY_HEADER = "Instant Pay via Stripe"
W2_STATUS_HEADER = "W-2 Status"


def load_workstream_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("workstream_config_must_be_object")
    return payload


def _public_base_url(config: dict[str, Any]) -> str:
    configured = str(os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    return str((config.get("landing") or {}).get("public_base_url_fallback") or "https://vettedcare.ai").rstrip("/")


def _workstream_headers(config: dict[str, Any], access_token: str) -> dict[str, str]:
    header_cfg = config.get("job_post_headers") or {}
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        INSTANT_PAY_HEADER: str(header_cfg.get("instant_pay_via_stripe") or "enabled"),
        W2_STATUS_HEADER: str(header_cfg.get("w2_status") or "Tier 1 W-2 Employee"),
    }


def build_baltimore_cna_job_post(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_workstream_config()
    landing = build_baltimore_instant_pay_landing_page()
    landing_cfg = cfg.get("landing") or {}
    location_cfg = cfg.get("location") or {}
    distribution_cfg = cfg.get("distribution") or {}
    webhook_cfg = cfg.get("webhook") or {}
    headers_cfg = cfg.get("job_post_headers") or {}

    base_url = _public_base_url(cfg)
    apply_path = str(landing_cfg.get("apply_path") or f"/{LANDING_SLUG}/")
    apply_url = f"{base_url}{apply_path}"
    webhook_path = str(webhook_cfg.get("path") or "/api/v1/webhooks/workstream/text-apply")
    webhook_url = f"{base_url}{webhook_path}"

    instant_point = next(
        (item for item in landing["selling_points"] if item["id"] == "instant_stripe_payout"),
        {},
    )
    w2_point = next(
        (item for item in landing["selling_points"] if item["id"] == "w2_compliance"),
        {},
    )

    title = str((cfg.get("position") or {}).get("title") or landing["headline"])
    overview_lines = [
        landing["subheadline"],
        "",
        f"• {instant_point.get('title', 'Instant shift payout')}: {instant_point.get('body', '')}",
        f"• {w2_point.get('title', 'W-2 compliance')}: {w2_point.get('body', '')}",
        "",
        f"Text-to-apply or visit {apply_url}",
    ]
    overview = "\n".join(line for line in overview_lines if line is not None)

    channels = list(distribution_cfg.get("channels") or ["indeed", "ziprecruiter"])
    return {
        "template_id": cfg.get("template_id"),
        "landing_slug": LANDING_SLUG,
        "position": {
            "title": title,
            "overview": overview,
            "status": str((cfg.get("position") or {}).get("status") or "published"),
            "access": str((cfg.get("position") or {}).get("access") or "public"),
            "job_type": str((cfg.get("position") or {}).get("job_type") or "part_time"),
            "pay_amount": str(landing.get("typical_hourly_pay") or "24"),
            "pay_frequency": str((cfg.get("position") or {}).get("pay_frequency") or "hourly"),
            "remote_type": str((cfg.get("position") or {}).get("remote_type") or "on_site"),
            "credential_type": landing["apply_defaults"]["credential_type"],
            "application_method": "text_to_apply",
            "apply_url": apply_url,
            "text_apply_keyword": str((cfg.get("position") or {}).get("text_apply_keyword") or "CNA"),
        },
        "location": {
            "name": str(location_cfg.get("name") or "Baltimore Metro"),
            "city": str(location_cfg.get("city") or "Baltimore"),
            "state": str(location_cfg.get("state") or "Maryland"),
            "postal_code": str(location_cfg.get("postal_code") or "21201"),
            "country": str(location_cfg.get("country") or "US"),
        },
        "distribution": {
            "channels": channels,
            "market": str(location_cfg.get("market") or "Baltimore"),
            "radius_miles": int(distribution_cfg.get("radius_miles") or 35),
            "text_to_apply_enabled": bool(distribution_cfg.get("text_to_apply_enabled", True)),
        },
        "custom_headers": {
            INSTANT_PAY_HEADER: str(headers_cfg.get("instant_pay_via_stripe") or "enabled"),
            W2_STATUS_HEADER: str(headers_cfg.get("w2_status") or "Tier 1 W-2 Employee"),
        },
        "webhook": {
            "url": webhook_url,
            "events": list(webhook_cfg.get("events") or ["text_to_apply_reply", "position_application.created"]),
            "destination_table": "caregiver_intake_queue",
        },
    }


def _channel_payloads(job_post: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    channels = job_post.get("distribution", {}).get("channels") or []
    channel_labels = (config.get("distribution") or {}).get("channel_labels") or {}
    payloads: list[dict[str, Any]] = []
    for channel in channels:
        label = str(channel_labels.get(channel) or channel.title())
        payloads.append(
            {
                "channel": channel,
                "channel_label": label,
                "position": job_post["position"],
                "location": job_post["location"],
                "custom_headers": job_post["custom_headers"],
                "webhook_url": job_post["webhook"]["url"],
                "referer_source": label,
            }
        )
    return payloads


def write_job_post_export(job_post: dict[str, Any], output_path: Path | None = None) -> Path:
    destination = output_path or DEFAULT_EXPORT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(job_post, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote Workstream job post export to %s", destination)
    return destination


def fetch_workstream_access_token(
    *,
    client_id: str,
    client_secret: str,
    api_base: str,
    scopes: list[str] | None = None,
    client: httpx.Client | None = None,
) -> str:
    owns_client = client is None
    http = client or httpx.Client(timeout=60.0)
    try:
        response = http.post(
            f"{api_base.rstrip('/')}/tokens",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scopes": scopes or ["positions", "position_applications"],
            },
        )
        response.raise_for_status()
        token = str(response.json().get("access_token") or "").strip()
        if not token:
            raise ValueError("workstream_token_missing")
        return token
    finally:
        if owns_client:
            http.close()


def push_job_post_to_workstream(
    job_post: dict[str, Any],
    *,
    config: dict[str, Any],
    access_token: str,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    api_cfg = config.get("api") or {}
    api_base = str(os.environ.get("WORKSTREAM_API_BASE") or api_cfg.get("base_url") or "https://public-api.workstream.us").rstrip("/")
    create_path = str(api_cfg.get("create_position_path") or "/positions")
    distribute_path = str(api_cfg.get("distribute_path") or "/positions/distribute")

    request_body = {
        "position": job_post["position"],
        "location": job_post["location"],
        "distribution": job_post["distribution"],
        "custom_headers": job_post["custom_headers"],
        "webhook": job_post["webhook"],
    }
    headers = _workstream_headers(config, access_token)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "api_base": api_base,
            "create_url": f"{api_base}{create_path}",
            "distribute_url": f"{api_base}{distribute_path}",
            "request_headers": headers,
            "request_body": request_body,
            "channel_payloads": _channel_payloads(job_post, config),
        }

    owns_client = client is None
    http = client or httpx.Client(timeout=90.0)
    try:
        create_response = http.post(
            f"{api_base}{create_path}",
            headers=headers,
            json=request_body,
        )
        create_response.raise_for_status()
        created = create_response.json()

        digest_key = (
            str(created.get("position", {}).get("digest_key") or "")
            or str(created.get("digest_key") or "")
        )
        distribute_body = {
            "position_digest_key": digest_key or None,
            "channels": job_post["distribution"]["channels"],
            "custom_headers": job_post["custom_headers"],
            "webhook_url": job_post["webhook"]["url"],
        }
        distribute_response = http.post(
            f"{api_base}{distribute_path}",
            headers=headers,
            json=distribute_body,
        )
        distribute_response.raise_for_status()
        distributed = distribute_response.json()
        return {
            "ok": True,
            "dry_run": False,
            "position_digest_key": digest_key,
            "create_response": created,
            "distribute_response": distributed,
            "channels": job_post["distribution"]["channels"],
        }
    finally:
        if owns_client:
            http.close()


def run_workstream_baltimore_cna_distribution(
    *,
    config_path: Path | None = None,
    export_path: Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    config = load_workstream_config(config_path)
    job_post = build_baltimore_cna_job_post(config)
    export_file = write_job_post_export(job_post, export_path)

    env_dry_run = str(os.environ.get("WORKSTREAM_JOB_DISTRIBUTION_DRY_RUN", "true")).lower() in {"1", "true", "yes"}
    effective_dry_run = env_dry_run if dry_run is None else dry_run

    client_id = str(os.environ.get("WORKSTREAM_CLIENT_ID") or "").strip()
    client_secret = str(os.environ.get("WORKSTREAM_CLIENT_SECRET") or "").strip()
    access_token = str(os.environ.get("WORKSTREAM_ACCESS_TOKEN") or "").strip()

    push_result: dict[str, Any]
    if effective_dry_run or not (access_token or (client_id and client_secret)):
        if not access_token and client_id and client_secret and not effective_dry_run:
            access_token = fetch_workstream_access_token(
                client_id=client_id,
                client_secret=client_secret,
                api_base=str((config.get("api") or {}).get("base_url") or "https://public-api.workstream.us"),
                scopes=list((config.get("api") or {}).get("token_scopes") or ["positions", "position_applications"]),
            )
        token_for_preview = access_token or "dry-run-token"
        push_result = push_job_post_to_workstream(
            job_post,
            config=config,
            access_token=token_for_preview,
            dry_run=True,
        )
        push_result["note"] = "Dry-run preview — set WORKSTREAM_ACCESS_TOKEN or client credentials for live push"
    else:
        if not access_token:
            access_token = fetch_workstream_access_token(
                client_id=client_id,
                client_secret=client_secret,
                api_base=str((config.get("api") or {}).get("base_url") or "https://public-api.workstream.us"),
                scopes=list((config.get("api") or {}).get("token_scopes") or ["positions", "position_applications"]),
            )
        push_result = push_job_post_to_workstream(
            job_post,
            config=config,
            access_token=access_token,
            dry_run=False,
        )

    return {
        "ok": True,
        "landing_slug": LANDING_SLUG,
        "apply_url": job_post["position"]["apply_url"],
        "webhook_url": job_post["webhook"]["url"],
        "export_json": str(export_file),
        "channels": job_post["distribution"]["channels"],
        "custom_headers": job_post["custom_headers"],
        "push": push_result,
    }
