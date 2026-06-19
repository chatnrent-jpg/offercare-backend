"""VMS shift ingestion worker — ShiftWise / Fieldglass polling and offer creation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarylandFacility, OfferCareJobOffer, VmsShiftIngestionLog
from app.services.care_taxonomy import normalize_shift_role
from app.services.job_board_crisis_scraper import match_facility_name
from app.services.live_scraper_http import request_live_scraper
from app.services.live_scraper_urls import effective_live_scraper_url
from app.services.ops_metrics import log_ops_event
from app.services.shift_schedule import set_offer_shift_schedule
from app.services.vms_types import VmsShiftRecord


def _fetch_vms_shifts_http() -> list[VmsShiftRecord]:
    url = effective_live_scraper_url("vms_ingest")
    if not url:
        raise RuntimeError("VMS_INGEST_URL is not configured")
    response = request_live_scraper(
        method="GET",
        url=url,
        timeout=settings.VMS_INGEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("shifts") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise RuntimeError("unexpected_vms_ingest_payload")
    records: list[VmsShiftRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        starts_raw = row.get("shift_starts_at")
        starts_at = datetime.fromisoformat(starts_raw) if starts_raw else datetime.now(timezone.utc)
        records.append(
            VmsShiftRecord(
                external_id=str(row.get("external_id") or f"http-{index}"),
                facility_name=str(row.get("facility_name") or "").strip(),
                shift_role=str(row.get("shift_role") or "CNA").strip().upper(),
                hourly_pay_rate=float(row.get("hourly_pay_rate") or 0),
                shift_starts_at=starts_at,
                source=str(row.get("source") or "VMS_HTTP").strip().upper(),
            )
        )
    return [row for row in records if row.facility_name and row.hourly_pay_rate > 0]


def ingest_vms_shifts() -> list[VmsShiftRecord]:
    """Poll partner VMS portals and normalize open shifts."""
    if settings.VMS_INGEST_DRY_RUN:
        from app.services.vms_playwright_worker import _dry_run_portal_shifts

        return _dry_run_portal_shifts()

    if settings.VMS_INGEST_PLAYWRIGHT_ENABLED:
        from app.services.vms_playwright_worker import scrape_vms_portals_playwright

        return scrape_vms_portals_playwright()

    return _fetch_vms_shifts_http()


def _existing_ingestion(db: Session, source: str, external_id: str) -> VmsShiftIngestionLog | None:
    return (
        db.query(VmsShiftIngestionLog)
        .filter(
            VmsShiftIngestionLog.source == source,
            VmsShiftIngestionLog.external_id == external_id,
        )
        .first()
    )


def persist_vms_shifts(db: Session, records: list[VmsShiftRecord]) -> dict:
    facilities = (
        db.query(MarylandFacility)
        .filter(MarylandFacility.state == "MD")
        .order_by(MarylandFacility.name.asc())
        .all()
    )
    offers_created = 0
    offers_skipped = 0
    no_facility = 0
    created_offer_ids: list[str] = []

    for record in records:
        if _existing_ingestion(db, record.source, record.external_id):
            offers_skipped += 1
            continue

        matched = match_facility_name(record.facility_name, facilities)
        payload_json = json.dumps(
            {
                "facility_name": record.facility_name,
                "shift_role": record.shift_role,
                "hourly_pay_rate": record.hourly_pay_rate,
                "shift_starts_at": record.shift_starts_at.isoformat(),
            }
        )
        if matched is None:
            no_facility += 1
            db.add(
                VmsShiftIngestionLog(
                    source=record.source,
                    external_id=record.external_id,
                    status="SKIPPED_NO_FACILITY",
                    shift_role=normalize_shift_role(record.shift_role),
                    hourly_pay_rate=record.hourly_pay_rate,
                    payload_json=payload_json,
                )
            )
            continue

        shift_role = normalize_shift_role(record.shift_role)
        offer = OfferCareJobOffer(
            facility_id=matched.facility_id,
            shift_role=shift_role,
            hourly_pay_rate=record.hourly_pay_rate,
            compliance_lock_status="BROADCASTING",
        )
        db.add(offer)
        db.flush()
        shift_end = record.shift_starts_at + timedelta(hours=settings.SHIFT_CALENDAR_DURATION_HOURS)
        set_offer_shift_schedule(
            offer,
            shift_starts_at=record.shift_starts_at,
            shift_ends_at=shift_end,
        )
        db.add(
            VmsShiftIngestionLog(
                source=record.source,
                external_id=record.external_id,
                facility_id=matched.facility_id,
                offer_id=offer.offer_id,
                status="INGESTED",
                shift_role=shift_role,
                hourly_pay_rate=record.hourly_pay_rate,
                payload_json=payload_json,
            )
        )
        offers_created += 1
        created_offer_ids.append(str(offer.offer_id))
        log_ops_event(
            db,
            event_type="VMS_SHIFT_INGEST",
            actor="vms_ingestion",
            entity_type="offer",
            entity_id=offer.offer_id,
            summary=f"Ingested {shift_role} shift from {record.source} for {matched.name}",
            metadata={"external_id": record.external_id, "hourly_pay_rate": record.hourly_pay_rate},
            commit=False,
        )

    db.commit()
    return {
        "shifts_fetched": len(records),
        "offers_created": offers_created,
        "offers_skipped": offers_skipped,
        "skipped_no_facility": no_facility,
        "created_offer_ids": created_offer_ids,
    }


def run_vms_ingestion(db: Session, *, persist: bool = True) -> dict:
    records = ingest_vms_shifts()
    result = {
        "shifts_fetched": len(records),
        "offers_created": 0,
        "offers_skipped": 0,
        "skipped_no_facility": 0,
        "created_offer_ids": [],
        "shifts": [
            {
                "external_id": row.external_id,
                "facility_name": row.facility_name,
                "shift_role": row.shift_role,
                "hourly_pay_rate": row.hourly_pay_rate,
                "shift_starts_at": row.shift_starts_at,
                "source": row.source,
            }
            for row in records
        ],
    }
    if persist and records:
        persisted = persist_vms_shifts(db, records)
        result.update(persisted)
    return result


def list_vms_ingestion_log(db: Session, *, limit: int = 50) -> list[dict]:
    rows = (
        db.query(VmsShiftIngestionLog, MarylandFacility)
        .outerjoin(MarylandFacility, MarylandFacility.facility_id == VmsShiftIngestionLog.facility_id)
        .order_by(VmsShiftIngestionLog.ingested_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "ingest_id": str(log.ingest_id),
            "source": log.source,
            "external_id": log.external_id,
            "status": log.status,
            "shift_role": log.shift_role,
            "hourly_pay_rate": float(log.hourly_pay_rate) if log.hourly_pay_rate is not None else None,
            "facility_name": facility.name if facility else None,
            "offer_id": str(log.offer_id) if log.offer_id else None,
            "ingested_at": log.ingested_at.isoformat() if log.ingested_at else None,
        }
        for log, facility in rows
    ]
