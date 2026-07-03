"""Submit locked placements to external VMS (dry-run by default)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.services.shift_schedule import resolve_offer_shift_window
from app.models import (
    ClinicalPlacementLedger,
    MarylandFacility,
    MarylandProvider,
    OfferCareJobOffer,
    VmsSubmissionLog,
)
from app.services.ops_metrics import log_ops_event

VMS_STATUS_LABELS = {
    "PENDING": "Queued for VMS dispatch",
    "SUBMITTED": "Confirmed with facility",
    "FAILED": "Dispatch review needed",
    "ESCROW_LOCKED": "Pay escrow locked",
}


def vms_status_label(status: str | None) -> str:
    key = str(status or "PENDING").upper()
    return VMS_STATUS_LABELS.get(key, key.replace("_", " ").title())


@dataclass(frozen=True)
class VmsSubmissionResult:
    placement_id: UUID
    status: str
    mode: str
    external_ref: str | None
    message: str


def build_vms_payload(
    placement: ClinicalPlacementLedger,
    offer: OfferCareJobOffer,
    provider: MarylandProvider,
    facility: MarylandFacility | None,
) -> dict:
    return {
        "placement_id": str(placement.placement_id),
        "offer_id": str(placement.offer_id),
        "facility_name": placement.facility_name,
        "facility_external_id": facility.external_id if facility else None,
        "clinical_unit": placement.clinical_unit,
        "hourly_bill_rate": float(placement.hourly_bill_rate),
        "clinician": {
            "provider_id": str(provider.provider_id),
            "full_name": provider.full_name,
            "npi_number": provider.npi_number,
            "md_license_number": provider.md_license_number,
            "license_status": provider.license_status,
        },
        "compliance_snapshot_token": placement.compliance_snapshot_token,
        "shift_role": offer.shift_role,
    }


def _vms_headers() -> dict[str, str]:
    token = str(settings.VMS_AUTH_TOKEN or "").strip()
    if not token:
        return {}
    header = str(settings.VMS_AUTH_HEADER or "Authorization").strip()
    if header.lower() == "authorization":
        return {"Authorization": f"Bearer {token}"}
    return {header: token}


def _parse_vms_response(response: httpx.Response) -> tuple[str | None, str]:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        body = response.json()
        if not isinstance(body, dict):
            return None, response.text[:500]
        external_ref = str(
            body.get("reference_id")
            or body.get("referenceId")
            or body.get("id")
            or body.get("placement_id")
            or ""
        ).strip() or None
        message = str(body.get("message") or body.get("status") or "Placement submitted to VMS.")
        return external_ref, message
    text = response.text.strip()
    return None, text[:500] if text else "Placement submitted to VMS."


def _post_to_vms(payload: dict) -> tuple[str, str, str | None, str]:
    if settings.VMS_DRY_RUN:
        external_ref = f"DRYRUN-{payload['placement_id'][:8].upper()}"
        return "SUBMITTED", "dry_run", external_ref, "Dry-run VMS submission."

    if not settings.vms_configured:
        raise ValueError("vms_not_configured")

    with httpx.Client(timeout=settings.VMS_SUBMISSION_TIMEOUT_SECONDS) as client:
        response = client.post(
            settings.VMS_SUBMISSION_URL,
            json=payload,
            headers=_vms_headers(),
        )
        response.raise_for_status()
        external_ref, message = _parse_vms_response(response)
        return "SUBMITTED", "live", external_ref, message


def submit_placement_to_vms(db: Session, placement_id: UUID) -> VmsSubmissionResult:
    placement = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.placement_id == placement_id)
        .with_for_update()
        .first()
    )
    if placement is None:
        raise ValueError("placement_not_found")
    if str(placement.vms_submission_status).upper() == "SUBMITTED":
        raise ValueError("already_submitted")

    offer = db.query(OfferCareJobOffer).filter(OfferCareJobOffer.offer_id == placement.offer_id).first()
    provider = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.provider_id == placement.assigned_clinician_id)
        .first()
    )
    facility = None
    if offer is not None:
        facility = (
            db.query(MarylandFacility)
            .filter(MarylandFacility.facility_id == offer.facility_id)
            .first()
        )
    if offer is None or provider is None:
        raise ValueError("placement_incomplete")

    payload = build_vms_payload(placement, offer, provider, facility)
    try:
        status, mode, external_ref, message = _post_to_vms(payload)
    except Exception as exc:  # noqa: BLE001
        status, mode, external_ref = "FAILED", "error", None
        message = str(exc)

    placement.vms_submission_status = status
    if status == "SUBMITTED":
        placement.vms_external_ref = external_ref
        placement.vms_submitted_at = datetime.now(timezone.utc)

    log = VmsSubmissionLog(
        placement_id=placement.placement_id,
        status=status,
        mode=mode,
        request_payload=json.dumps(payload),
        response_message=message,
        external_ref=external_ref,
    )
    db.add(log)
    db.commit()
    log_ops_event(
        db,
        event_type="VMS_SUBMIT",
        actor="vms_integration",
        entity_type="placement",
        entity_id=placement.placement_id,
        summary=f"VMS submission {status} for {placement.facility_name}",
        metadata={"mode": mode, "external_ref": external_ref, "message": message},
    )

    return VmsSubmissionResult(
        placement_id=placement.placement_id,
        status=status,
        mode=mode,
        external_ref=external_ref,
        message=message,
    )


def submit_pending_placements(db: Session, *, limit: int = 25) -> list[VmsSubmissionResult]:
    rows = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.vms_submission_status == "PENDING")
        .order_by(ClinicalPlacementLedger.outbound_payload_timestamp.asc())
        .limit(limit)
        .all()
    )
    results: list[VmsSubmissionResult] = []
    for row in rows:
        try:
            results.append(submit_placement_to_vms(db, row.placement_id))
        except ValueError as exc:
            if str(exc) == "already_submitted":
                continue
            results.append(
                VmsSubmissionResult(
                    placement_id=row.placement_id,
                    status="FAILED",
                    mode="error",
                    external_ref=None,
                    message=str(exc),
                )
            )
    return results


def run_vms_connectivity_test() -> dict:
    probe_payload = {
        "placement_id": "00000000-0000-0000-0000-000000000000",
        "event": "offercare_connectivity_test",
        "region": "Maryland",
        "source": "offercare.ai",
    }
    try:
        status, mode, external_ref, message = _post_to_vms(probe_payload)
        return {
            "status": status,
            "mode": mode,
            "external_ref": external_ref,
            "message": message,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "FAILED",
            "mode": "error",
            "external_ref": None,
            "message": str(exc),
        }


def list_placements(
    db: Session,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query = (
        db.query(ClinicalPlacementLedger, MarylandProvider)
        .join(MarylandProvider, ClinicalPlacementLedger.assigned_clinician_id == MarylandProvider.provider_id)
        .order_by(ClinicalPlacementLedger.outbound_payload_timestamp.desc())
    )
    if status:
        query = query.filter(ClinicalPlacementLedger.vms_submission_status == status.upper())
    rows = query.limit(limit).all()
    return [
        {
            "placement_id": placement.placement_id,
            "offer_id": placement.offer_id,
            "facility_name": placement.facility_name,
            "clinical_unit": placement.clinical_unit,
            "hourly_bill_rate": float(placement.hourly_bill_rate),
            "assigned_clinician_id": placement.assigned_clinician_id,
            "clinician_name": provider.full_name,
            "vms_submission_status": placement.vms_submission_status,
            "vms_external_ref": placement.vms_external_ref,
            "outbound_payload_timestamp": placement.outbound_payload_timestamp,
        }
        for placement, provider in rows
    ]


def list_clinician_placements(
    db: Session,
    provider_id: UUID,
    *,
    limit: int = 25,
) -> list[dict]:
    rows = (
        db.query(ClinicalPlacementLedger, OfferCareJobOffer)
        .join(OfferCareJobOffer, ClinicalPlacementLedger.offer_id == OfferCareJobOffer.offer_id)
        .filter(ClinicalPlacementLedger.assigned_clinician_id == provider_id)
        .order_by(ClinicalPlacementLedger.placement_id.desc())
        .limit(limit)
        .all()
    )
    results: list[dict] = []
    for placement, offer in rows:
        shift_starts_at, shift_ends_at = resolve_offer_shift_window(
            offer,
            fallback_anchor=placement.outbound_payload_timestamp,
        )
        results.append(
            {
                "placement_id": placement.placement_id,
                "offer_id": placement.offer_id,
                "facility_name": placement.facility_name,
                "clinical_unit": placement.clinical_unit,
                "hourly_bill_rate": float(placement.hourly_bill_rate),
                "vms_submission_status": placement.vms_submission_status,
                "vms_status_label": vms_status_label(placement.vms_submission_status),
                "vms_external_ref": placement.vms_external_ref,
                "vms_submitted_at": placement.vms_submitted_at,
                "shift_starts_at": shift_starts_at,
                "shift_ends_at": shift_ends_at,
                "outbound_payload_timestamp": placement.outbound_payload_timestamp,
            }
        )
    return results


def submit_demo_clinician_placements_to_vms(db: Session, provider: MarylandProvider) -> int:
    """Dry-run/live VMS dispatch for demo walkthrough placements stuck in PENDING."""
    from app.services.shift_matching import is_demo_walkthrough_provider

    if not is_demo_walkthrough_provider(provider):
        return 0

    submitted = 0
    rows = list_clinician_placements(db, provider.provider_id)
    for row in rows:
        if str(row.get("vms_submission_status") or "").upper() != "PENDING":
            continue
        try:
            submit_placement_to_vms(db, row["placement_id"])
            submitted += 1
        except ValueError:
            continue
    return submitted
