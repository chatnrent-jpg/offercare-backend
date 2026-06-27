"""Load Montgomery SNF CNA production slice from PostgreSQL for desk orchestrator."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import MdMarketFacility, MdProviderCompliance, MarylandProvider, OfferCareJobOffer
from app.services.vetted_status import VETTED_CLEAR, compute_vetted_status
from strategy.desk_orchestrator import DeskOrchestrator

SLICE_COUNTY = "Montgomery"
SLICE_FACILITY_TYPE = "SNF"
SLICE_ROLE = "CNA"
SLICE_FACILITY_NAME = "Arbor Ridge at Riderwood"
SLICE_MD_LICENSE = "MD-SNF-215343"


def _normalize_county(value: str) -> str:
    token = re.sub(r"\s+county\s*$", "", str(value or "").strip(), flags=re.IGNORECASE)
    return token.lower()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_to_applicant(
    provider: MarylandProvider,
    compliance: MdProviderCompliance | None,
    *,
    placement_eligible: bool,
) -> dict[str, Any]:
    credential = str(provider.credential_type or "").upper()
    has_gna = bool(compliance.has_gna_endorsement) if compliance else credential == "GNA"
    verified = provider.last_verified_timestamp or provider.applied_at or datetime.now(timezone.utc)
    return {
        "name": provider.full_name,
        "license_type": "CNA" if credential in {"CNA", "GNA"} else credential,
        "license_number": provider.md_license_number,
        "has_gna_endorsement": has_gna,
        "county": (compliance.home_county if compliance and compliance.home_county else SLICE_COUNTY),
        "compliant": str(compliance.compliance_status if compliance else "COMPLIANT").upper() == "COMPLIANT",
        "placement_eligible": placement_eligible,
        "compliance_status": compliance.compliance_status if compliance else "COMPLIANT",
        "verification_timestamp": verified.isoformat() if hasattr(verified, "isoformat") else str(verified),
    }


def load_workforce_registry(db: Session) -> dict[str, Any]:
    rows = (
        db.query(MarylandProvider, MdProviderCompliance)
        .outerjoin(MdProviderCompliance, MdProviderCompliance.provider_id == MarylandProvider.provider_id)
        .filter(MarylandProvider.state == "MD")
        .filter(MarylandProvider.credential_type.in_(["CNA", "GNA"]))
        .all()
    )

    applicants: list[dict[str, Any]] = []
    for provider, compliance in rows:
        county = compliance.home_county if compliance and compliance.home_county else ""
        if _normalize_county(county) != _normalize_county(SLICE_COUNTY):
            continue
        placement_eligible = compute_vetted_status(db, provider) == VETTED_CLEAR
        applicants.append(_provider_to_applicant(provider, compliance, placement_eligible=placement_eligible))

    return {
        "mode": "PRODUCTION_SLICE",
        "live_execution": True,
        "slice": f"{SLICE_COUNTY}_{SLICE_FACILITY_TYPE}_{SLICE_ROLE}",
        "applicants": applicants,
    }


def load_facility_shift(db: Session) -> dict[str, Any]:
    facility = (
        db.query(MdMarketFacility)
        .filter(MdMarketFacility.state == "MD")
        .filter(MdMarketFacility.facility_type == SLICE_FACILITY_TYPE)
        .filter(MdMarketFacility.md_license_number == SLICE_MD_LICENSE)
        .first()
    )
    if facility is None:
        facility = (
            db.query(MdMarketFacility)
            .filter(MdMarketFacility.company_name.ilike(f"%{SLICE_FACILITY_NAME.split()[0]}%"))
            .filter(MdMarketFacility.facility_type == SLICE_FACILITY_TYPE)
            .first()
        )
    if facility is None:
        raise ValueError(
            f"production facility not found for slice ({SLICE_FACILITY_NAME}). "
            "Run scripts/seed_montgomery_snf_cna_slice.py and scripts/import_md_facilities_scraped.py."
        )

    offer = None
    if facility.maryland_facility_id:
        offer = (
            db.query(OfferCareJobOffer)
            .filter(OfferCareJobOffer.facility_id == facility.maryland_facility_id)
            .filter(OfferCareJobOffer.shift_role.in_(["CNA", "GNA", "NURSING_ASSISTANT"]))
            .order_by(OfferCareJobOffer.created_at.desc())
            .first()
        )

    if offer and offer.shift_starts_at:
        shift_start = offer.shift_starts_at.astimezone(timezone.utc)
        order_id = str(offer.offer_id)
    else:
        shift_start = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1)
        order_id = f"prod-{str(facility.facility_id)[:8]}"

    return {
        "order_id": order_id,
        "facility_id": str(facility.facility_id),
        "facility_name": facility.company_name,
        "facility_type": facility.facility_type,
        "county": facility.md_county,
        "required_role": SLICE_ROLE,
        "shift_timestamp": shift_start.isoformat(),
        "md_license_number": facility.md_license_number,
        "live_execution": True,
    }


def load_active_commitments(db: Session) -> list[dict[str, Any]]:
    commitments: list[dict[str, Any]] = []
    offers = (
        db.query(OfferCareJobOffer, MarylandProvider, MdMarketFacility)
        .join(MarylandProvider, OfferCareJobOffer.assigned_provider_id == MarylandProvider.provider_id)
        .join(MdMarketFacility, MdMarketFacility.maryland_facility_id == OfferCareJobOffer.facility_id)
        .filter(OfferCareJobOffer.assigned_provider_id.isnot(None))
        .filter(MdMarketFacility.md_county.ilike(f"{SLICE_COUNTY}%"))
        .all()
    )

    for offer, provider, facility in offers:
        if not offer.shift_starts_at:
            continue
        start = offer.shift_starts_at.astimezone(timezone.utc)
        end = (
            offer.shift_ends_at.astimezone(timezone.utc)
            if offer.shift_ends_at
            else start + timedelta(hours=8)
        )
        commitments.append(
            {
                "provider_id": provider.md_license_number,
                "provider_name": provider.full_name,
                "order_id": str(offer.offer_id),
                "facility_name": facility.company_name,
                "county": facility.md_county,
                "shift_start": start.isoformat(),
                "shift_end": end.isoformat(),
            }
        )
    return commitments


def load_montgomery_snf_cna_slice(db: Session) -> dict[str, Any]:
    registry = load_workforce_registry(db)
    shift = load_facility_shift(db)
    commitments = load_active_commitments(db)
    if not registry.get("applicants"):
        raise ValueError(
            "no Montgomery CNA/GNA providers in PostgreSQL for production slice. "
            "Run scripts/seed_montgomery_snf_cna_slice.py."
        )
    return {
        "slice_key": f"{SLICE_COUNTY}_{SLICE_FACILITY_TYPE}_{SLICE_ROLE}",
        "live_execution": True,
        "mode": "PRODUCTION_SLICE",
        "workforce_registry": registry,
        "shift": shift,
        "commitments": commitments,
        "loaded_at_utc": _utc_now_iso(),
    }


def run_production_desk_cycle(
    db: Session,
    *,
    evaluation_timestamp: str | None = None,
    request_timestamp: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    slice_payload = load_montgomery_snf_cna_slice(db)
    evaluation_ts = evaluation_timestamp or _utc_now_iso()

    market = (
        db.query(MdMarketFacility)
        .filter(MdMarketFacility.md_license_number == SLICE_MD_LICENSE)
        .first()
    )
    maryland_facility_id = market.maryland_facility_id if market else None

    orchestrator = DeskOrchestrator(
        slice_payload["workforce_registry"],
        active_commitments=slice_payload["commitments"],
        db=db,
        facility_id=maryland_facility_id,
    )
    desk_run = orchestrator.run_full_desk_cycle(
        slice_payload["shift"],
        evaluation_timestamp=evaluation_ts,
        request_timestamp=request_timestamp,
        facility_id=SLICE_MD_LICENSE,
    )

    envelope = {
        "run_id": f"desk-prod-{evaluation_ts}",
        "staged_at_utc": _utc_now_iso(),
        "live_execution": True,
        "mode": "PRODUCTION_SLICE",
        "pipeline": "full",
        "slice_key": slice_payload["slice_key"],
        "status": desk_run.get("booking", {}).get("status"),
        "result": desk_run,
        "db_source": {
            "facility": slice_payload["shift"].get("facility_name"),
            "provider_count": len(slice_payload["workforce_registry"].get("applicants") or []),
            "commitment_count": len(slice_payload["commitments"]),
            "matcher_source": orchestrator.matcher_source,
            "matcher_core": "strategy/shift_match_core.py",
        },
    }

    if persist:
        from pathlib import Path

        log_path = Path(__file__).resolve().parents[2] / "logs" / "manus" / "desk_pipeline_runs.json"
        DeskOrchestrator.persist_run(envelope, log_path)

    return {
        "ok": True,
        "run_id": envelope["run_id"],
        "pipeline": "full",
        "status": envelope["status"],
        "live_execution": True,
        "mode": "PRODUCTION_SLICE",
        "slice_key": slice_payload["slice_key"],
        "result": desk_run,
        "db_source": envelope["db_source"],
    }


def run_production_live_callout(
    db: Session,
    *,
    original_provider_id: str = "CNA-MD-88421",
) -> dict[str, Any]:
    from app.config import settings
    from strategy.backup_routing_engine import BackupRoutingEngine

    if not settings.MD_MONTGOMERY_SNF_CNA_LIVE_DISPATCH:
        raise ValueError(
            "Montgomery SNF CNA live dispatch is disabled. "
            "Set MD_MONTGOMERY_SNF_CNA_LIVE_DISPATCH=true in .env."
        )

    slice_payload = load_montgomery_snf_cna_slice(db)
    shift = dict(slice_payload["shift"])
    disrupted_shift_id = str(shift.get("order_id") or "")

    router = BackupRoutingEngine(slice_payload["workforce_registry"])
    dispatch = router.trigger_backup_routing(
        disrupted_shift_id=disrupted_shift_id,
        original_provider_id=original_provider_id,
        shift_override=shift,
        live_execution=True,
        slice_key=slice_payload["slice_key"],
    )

    from app.services.md_backup_notify_cascade import notify_montgomery_backup_cascade

    notify_result = notify_montgomery_backup_cascade(db, dispatch)

    return {
        "ok": True,
        "live_execution": True,
        "mode": "PRODUCTION_SLICE",
        "slice_key": slice_payload["slice_key"],
        "dispatch": dispatch,
        "facility": shift.get("facility_name"),
        "original_provider_id": original_provider_id,
        "notify_cascade": notify_result,
    }
