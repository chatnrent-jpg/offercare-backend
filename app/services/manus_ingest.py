"""Manus autonomous vetting run ingestion — Manus acts, VettedMe decides."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import ExclusionScreening, LicenseVerificationLog, ManusVettingRun, MarylandProvider
from app.services.credentialing_pipeline import run_full_credentialing_screen
from app.services.vetted_audit import log_vetted_event
from app.services.vetted_monitor import run_vettedme_safety_cycle
from app.services.vetted_status import build_provider_vetted_profile, sync_provider_vetted_status

_CHECK_TO_SCREENING = {
    "OIG": "OIG",
    "OIG_LEIE": "OIG",
    "MBON": "MBON",
    "MD_JUDICIARY": "JUDICIARY",
    "JUDICIARY": "JUDICIARY",
}

_PASS_RESULTS = {"PASS", "CLEAR", "OK", "VERIFIED"}
_FAIL_RESULTS = {"FAIL", "BLOCKED", "EXCLUDED", "DENIED", "FLAGGED"}


def _resolve_provider(db: Session, payload: dict) -> MarylandProvider | None:
    provider_id = payload.get("provider_id")
    if provider_id:
        try:
            return db.query(MarylandProvider).filter(MarylandProvider.provider_id == UUID(str(provider_id))).first()
        except ValueError:
            return None

    npi = str(payload.get("npi_number") or "").strip()
    if npi:
        row = db.query(MarylandProvider).filter(MarylandProvider.npi_number == npi).first()
        if row:
            return row

    email = str(payload.get("email") or "").strip().lower()
    if email:
        return db.query(MarylandProvider).filter(MarylandProvider.email == email).first()

    license_no = str(payload.get("md_license_number") or "").strip()
    if license_no:
        return db.query(MarylandProvider).filter(MarylandProvider.md_license_number == license_no).first()

    return None


def _map_check_result(result: str) -> str:
    normalized = str(result or "UNKNOWN").upper()
    if normalized in _PASS_RESULTS:
        return "CLEAR"
    if normalized in _FAIL_RESULTS:
        return "EXCLUDED"
    if normalized in {"UNKNOWN", "PENDING", "REVIEW"}:
        return "PENDING"
    return normalized


def ingest_manus_vetting_run(db: Session, payload: dict, *, actor: str = "manus") -> dict:
    external_run_id = str(payload.get("run_id") or payload.get("external_run_id") or uuid4())
    provider = _resolve_provider(db, payload)
    checks = payload.get("checks") or []

    run = ManusVettingRun(
        external_run_id=external_run_id[:128],
        provider_id=provider.provider_id if provider else None,
        status="RECEIVED",
        checks_count=len(checks),
        summary=str(payload.get("summary") or "")[:500],
        payload_json=json.dumps(payload, default=str)[:8000],
    )
    db.add(run)
    db.flush()

    applied_checks: list[dict] = []
    if provider is None:
        run.status = "FAILED"
        run.applied_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "run_id": str(run.run_id),
            "external_run_id": external_run_id,
            "status": "FAILED",
            "error": "provider_not_found",
        }

    for check in checks:
        check_type = str(check.get("check_type") or check.get("type") or "UNKNOWN").upper()
        result = _map_check_result(str(check.get("result") or check.get("status") or "UNKNOWN"))
        notes = str(check.get("notes") or check.get("evidence") or "")[:500]
        source_url = str(check.get("source_url") or check.get("source") or "")[:200]

        db.add(
            LicenseVerificationLog(
                provider_id=provider.provider_id,
                event_type=f"MANUS_{check_type}",
                check_result=result,
                notes=notes or source_url or None,
                reviewer=actor,
            )
        )

        screening_source = _CHECK_TO_SCREENING.get(check_type)
        if screening_source:
            db.add(
                ExclusionScreening(
                    provider_id=provider.provider_id,
                    source=screening_source,
                    status="CLEAR" if result == "CLEAR" else ("EXCLUDED" if result == "EXCLUDED" else result),
                    payload_json=json.dumps(check, default=str)[:4000],
                )
            )

        applied_checks.append({"check_type": check_type, "result": result})

    if payload.get("run_full_screen"):
        run_full_credentialing_screen(db, provider.provider_id)

    previous = str(provider.vetted_status or "ACTION_NEEDED").upper()
    new_status, changed = sync_provider_vetted_status(db, provider, actor=actor)

    recommended = str(payload.get("recommended_status") or "").upper()
    if recommended and recommended != new_status:
        log_vetted_event(
            db,
            event_type="MANUS_RECOMMENDATION",
            provider_id=provider.provider_id,
            actor=actor,
            previous_status=new_status,
            new_status=recommended,
            summary=f"Manus recommended {recommended}; system computed {new_status}",
            metadata={"external_run_id": external_run_id},
        )

    log_vetted_event(
        db,
        event_type="MANUS_RUN_APPLIED",
        provider_id=provider.provider_id,
        actor=actor,
        previous_status=previous if changed else None,
        new_status=new_status,
        summary=f"Manus run applied — {len(applied_checks)} check(s)",
        metadata={"external_run_id": external_run_id, "checks": applied_checks},
        commit=False,
    )

    run.status = "APPLIED"
    run.applied_at = datetime.now(timezone.utc)
    db.commit()

    profile = build_provider_vetted_profile(db, provider.provider_id)
    return {
        "run_id": str(run.run_id),
        "external_run_id": external_run_id,
        "status": "APPLIED",
        "provider_id": str(provider.provider_id),
        "checks_applied": len(applied_checks),
        "vetted_status": profile["vetted_status"],
        "computed_status": profile["computed_status"],
        "status_changed": changed is not None,
    }


def run_manus_batch_and_cycle(db: Session, payloads: list[dict]) -> dict:
    results = [ingest_manus_vetting_run(db, item, actor="manus") for item in payloads]
    cycle = run_vettedme_safety_cycle(db, actor="manus_batch")
    return {"runs": results, "safety_cycle": cycle}
