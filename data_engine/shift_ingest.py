"""Manus VMS shift JSON ingestion — dedupe, validate, trigger lookahead matcher."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import IngestedOpenShift, MarylandFacility, OfferCareJobOffer
from data_engine.lookahead_shift_matcher import match_top_providers_for_shift

REQUIRED_SHIFT_FIELDS = (
    "facility_id",
    "shift_date",
    "unit_dept",
    "start_time",
    "shift_role",
    "hourly_pay_rate",
)


def shift_composite_hash(
    *,
    facility_id: str,
    shift_date: str,
    unit_dept: str,
    start_time: str,
) -> str:
    raw = f"{facility_id}|{shift_date}|{unit_dept}|{start_time}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_shift_datetime(shift_date: str, start_time: str) -> datetime | None:
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ):
        token = f"{shift_date} {start_time}".strip()
        try:
            parsed = datetime.strptime(token, fmt.replace("T%H", " %H"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(f"{shift_date}T{start_time}")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def validate_shift_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_SHIFT_FIELDS:
        if record.get(field) in (None, ""):
            errors.append(f"missing_{field}")
    return errors


def ingest_shift_record(db: Session, record: dict[str, Any], *, source: str = "manus_vms") -> dict[str, Any]:
    errors = validate_shift_record(record)
    if errors:
        return {"ok": False, "errors": errors, "record": record}

    facility_id = uuid.UUID(str(record["facility_id"]))
    facility = db.query(MarylandFacility).filter(MarylandFacility.facility_id == facility_id).first()
    if facility is None:
        return {"ok": False, "errors": ["facility_not_found"], "record": record}

    shift_date = str(record["shift_date"])
    unit_dept = str(record["unit_dept"])
    start_time = str(record["start_time"])
    composite = shift_composite_hash(
        facility_id=str(facility_id),
        shift_date=shift_date,
        unit_dept=unit_dept,
        start_time=start_time,
    )

    existing = (
        db.query(IngestedOpenShift)
        .filter(IngestedOpenShift.composite_hash == composite)
        .first()
    )
    if existing:
        return {
            "ok": True,
            "duplicate": True,
            "ingest_id": str(existing.ingest_id),
            "composite_hash": composite,
        }

    shift_starts_at = _parse_shift_datetime(shift_date, start_time)
    now = datetime.now(timezone.utc)
    if shift_starts_at is not None and shift_starts_at <= now:
        return {"ok": False, "errors": ["shift_not_in_future"], "record": record}

    pay_rate = float(record["hourly_pay_rate"])
    shift_role = str(record["shift_role"])

    offer = OfferCareJobOffer(
        offer_id=uuid.uuid4(),
        facility_id=facility_id,
        shift_role=shift_role,
        hourly_pay_rate=pay_rate,
        compliance_lock_status="BROADCASTING",
        shift_starts_at=shift_starts_at,
    )
    db.add(offer)
    db.flush()

    row = IngestedOpenShift(
        ingest_id=uuid.uuid4(),
        composite_hash=composite,
        facility_id=facility_id,
        offer_id=offer.offer_id,
        source=source,
        shift_date=shift_date,
        unit_dept=unit_dept,
        start_time=start_time,
        shift_role=shift_role,
        hourly_pay_rate=pay_rate,
        payload_json=json.dumps(record),
        status="INGESTED",
        ingested_at=now,
    )
    db.add(row)
    db.commit()

    matches = match_top_providers_for_shift(
        db,
        facility_id=facility_id,
        shift_role=shift_role,
        hourly_pay_rate=pay_rate,
        shift_starts_at=shift_starts_at,
        limit=3,
    )

    row.match_payload_json = json.dumps({"top_matches": matches})
    row.status = "MATCHED" if matches else "NO_MATCH"
    db.commit()

    return {
        "ok": True,
        "duplicate": False,
        "ingest_id": str(row.ingest_id),
        "offer_id": str(offer.offer_id),
        "composite_hash": composite,
        "top_matches": matches,
    }


def ingest_manus_shift_payload(db: Session, payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    records = payload if isinstance(payload, list) else list(payload.get("shifts") or [])
    results = [ingest_shift_record(db, dict(record)) for record in records]
    return {
        "count": len(results),
        "inserted": sum(1 for r in results if r.get("ok") and not r.get("duplicate")),
        "duplicates": sum(1 for r in results if r.get("duplicate")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }


def ingest_shifts_from_directory(db: Session) -> dict[str, Any]:
    from data_engine.paths import INCOMING_SHIFTS_DIR, PROCESSED_DIR, ensure_data_engine_dirs

    ensure_data_engine_dirs()
    batch_results: list[dict[str, Any]] = []
    for path in sorted(INCOMING_SHIFTS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = ingest_manus_shift_payload(db, payload)
        batch_results.append({"file": path.name, **result})
        dest = PROCESSED_DIR / "shifts" / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        path.replace(dest)
    return {"files": len(batch_results), "batches": batch_results}
