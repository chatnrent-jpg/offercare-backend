"""Playwright automation for ShiftWise / Fieldglass VMS partner portals."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.vms_types import VmsShiftRecord


def _dry_run_portal_shifts() -> list[VmsShiftRecord]:
    now = datetime.now(timezone.utc)
    tonight = now + timedelta(hours=6)
    return [
        VmsShiftRecord(
            external_id="shiftwise-fc-northpoint-cna-001",
            facility_name="FutureCare Northpoint",
            shift_role="CNA",
            hourly_pay_rate=34.0,
            shift_starts_at=tonight,
            source="SHIFTWISE",
        ),
        VmsShiftRecord(
            external_id="fieldglass-genesis-baltimore-lpn-002",
            facility_name="Genesis HealthCare Baltimore Center",
            shift_role="LPN",
            hourly_pay_rate=46.0,
            shift_starts_at=tonight + timedelta(hours=12),
            source="FIELDGLASS",
        ),
        VmsShiftRecord(
            external_id="shiftwise-communicare-cna-003",
            facility_name="CommuniCare Silver Spring",
            shift_role="CNA",
            hourly_pay_rate=31.5,
            shift_starts_at=tonight + timedelta(hours=18),
            source="SHIFTWISE",
        ),
    ]


def _parse_portal_json(payload: dict) -> list[VmsShiftRecord]:
    rows = payload.get("shifts") or payload.get("open_shifts") or []
    records: list[VmsShiftRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        starts_raw = row.get("shift_starts_at") or row.get("starts_at")
        starts_at = datetime.fromisoformat(starts_raw) if starts_raw else datetime.now(timezone.utc)
        records.append(
            VmsShiftRecord(
                external_id=str(row.get("external_id") or row.get("id") or f"portal-{index}"),
                facility_name=str(row.get("facility_name") or row.get("facility") or "").strip(),
                shift_role=str(row.get("shift_role") or row.get("role") or "CNA").strip().upper(),
                hourly_pay_rate=float(row.get("hourly_pay_rate") or row.get("pay_rate") or 0),
                shift_starts_at=starts_at,
                source=str(row.get("source") or "VMS_PORTAL").strip().upper(),
            )
        )
    return [row for row in records if row.facility_name and row.hourly_pay_rate > 0]


def scrape_vms_portals_playwright() -> list[VmsShiftRecord]:
    if settings.VMS_INGEST_DRY_RUN:
        return _dry_run_portal_shifts()

    portal_url = str(settings.VMS_INGEST_PORTAL_URL or "").strip()
    if not portal_url:
        raise RuntimeError("VMS_INGEST_PORTAL_URL is not configured for Playwright ingestion")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is not installed — pip install playwright && playwright install chromium") from exc

    username = str(settings.VMS_INGEST_PORTAL_USER or "").strip()
    password = str(settings.VMS_INGEST_PORTAL_PASSWORD or "").strip()
    if not username or not password:
        raise RuntimeError("VMS_INGEST_PORTAL_USER and VMS_INGEST_PORTAL_PASSWORD are required")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(portal_url, wait_until="networkidle", timeout=int(settings.VMS_INGEST_PLAYWRIGHT_TIMEOUT_SECONDS * 1000))
        page.fill(settings.VMS_INGEST_PORTAL_USER_SELECTOR, username)
        page.fill(settings.VMS_INGEST_PORTAL_PASSWORD_SELECTOR, password)
        page.click(settings.VMS_INGEST_PORTAL_SUBMIT_SELECTOR)
        page.wait_for_load_state("networkidle", timeout=int(settings.VMS_INGEST_PLAYWRIGHT_TIMEOUT_SECONDS * 1000))
        page.wait_for_selector(settings.VMS_INGEST_PORTAL_SHIFTS_SELECTOR, timeout=int(settings.VMS_INGEST_PLAYWRIGHT_TIMEOUT_SECONDS * 1000))
        raw_json = page.eval_on_selector(
            settings.VMS_INGEST_PORTAL_SHIFTS_SELECTOR,
            "el => el.textContent",
        )
        browser.close()

    payload = json.loads(raw_json or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected_vms_portal_payload")
    return _parse_portal_json(payload)
