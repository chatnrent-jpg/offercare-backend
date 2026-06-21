"""Maryland CNA/LPN nursing home worker inflow landing content and apply flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import MarylandProvider
from app.schemas import ClinicianApplyRequest, MarylandLandingApplyRequest
from app.services.care_taxonomy import (
    SHIFT_TEMPLATES_BY_FACILITY_TYPE,
    credential_label,
    default_service_lines_for_credential,
    normalize_credential_type,
)
from app.services.credentialing_pipeline import run_full_credentialing_screen
from app.services.license_verification import apply_as_clinician
from app.services.worker_consent import build_consent_disclosures, record_apply_consents
from app.services.worker_privacy_policy import build_worker_privacy_policy
from app.services.worker_terms_of_service import build_worker_terms_of_service


MARYLAND_LANDING_CREDENTIALS: tuple[str, ...] = ("CNA", "LPN", "GNA")


@dataclass(frozen=True)
class MarylandPayBand:
    credential_type: str
    label: str
    typical_hourly_pay: float
    suggested_minimum: float


def maryland_pay_bands() -> list[MarylandPayBand]:
    templates = SHIFT_TEMPLATES_BY_FACILITY_TYPE.get("NURSING_HOME", ())
    by_role = {role: rate for role, rate in templates}
    bands: list[MarylandPayBand] = []
    for credential in MARYLAND_LANDING_CREDENTIALS:
        typical = float(by_role.get(credential, by_role.get("CNA", 22.0)))
        bands.append(
            MarylandPayBand(
                credential_type=credential,
                label=credential_label(credential),
                typical_hourly_pay=typical,
                suggested_minimum=round(typical * 0.85, 2),
            )
        )
    return bands


def build_maryland_landing_page() -> dict:
    return {
        "headline": "Emergency CNA & LPN shifts for Maryland nursing homes",
        "subheadline": (
            "Flexible per-diem floor coverage with W-2 employment, weekly direct deposit, "
            "and instant Maryland Board of Nursing verification."
        ),
        "value_props": [
            "Fill open shifts within 15 minutes of your home — no long-term contract",
            "W-2 employment — not 1099 contractor misclassification",
            "Automated MBON, OIG LEIE, and Maryland judiciary screening before your first shift",
            "Urgent SMS dispatch when a local nursing home needs floor staff tonight",
        ],
        "comar_note": (
            "Maryland nursing homes must maintain a 1:15 staffing ratio under COMAR 10.07.02.19. "
            "We help facilities stay compliant when aides call out."
        ),
        "credentials": [
            {
                "code": band.credential_type,
                "label": band.label,
                "typical_hourly_pay": band.typical_hourly_pay,
                "suggested_minimum": band.suggested_minimum,
            }
            for band in maryland_pay_bands()
        ],
        "apply_defaults": {
            "state": "MD",
            "service_lines": "NURSING_HOME",
        },
        "portal_url": "/portal",
        "consent_disclosures": build_consent_disclosures(),
        "terms_of_service": build_worker_terms_of_service(),
        "privacy_policy": build_worker_privacy_policy(),
    }


def apply_maryland_floor_staff(
    db: Session,
    payload: MarylandLandingApplyRequest,
    *,
    client_ip: str | None = None,
) -> dict:
    credential_type = normalize_credential_type(payload.credential_type)
    if credential_type not in MARYLAND_LANDING_CREDENTIALS:
        raise ValueError("unsupported_credential")

    apply_payload = ClinicianApplyRequest(
        full_name=payload.full_name.strip(),
        email=str(payload.email).strip().lower(),
        phone_number=payload.phone_number.strip(),
        npi_number=payload.npi_number,
        md_license_number=payload.md_license_number.strip().upper(),
        state="MD",
        credential_type=credential_type,
        service_lines=payload.service_lines or default_service_lines_for_credential(credential_type),
        min_hourly_rate=payload.min_hourly_rate,
        response_propensity=payload.response_propensity,
        fatigue_score=0.0,
        password=payload.password,
    )
    provider, auto_check = apply_as_clinician(db, apply_payload)
    if payload.home_zip:
        provider.home_zip = payload.home_zip.strip()
        db.flush()

    record_apply_consents(
        db,
        provider.provider_id,
        consent_version=payload.consent_version,
        client_ip=client_ip,
    )

    screen = run_full_credentialing_screen(db, provider.provider_id)
    refreshed = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider.provider_id).one()
    return {
        "provider_id": str(refreshed.provider_id),
        "full_name": refreshed.full_name,
        "email": refreshed.email,
        "credential_type": refreshed.credential_type,
        "license_status": refreshed.license_status,
        "dispatch_status": refreshed.dispatch_status,
        "auto_check_result": auto_check.result,
        "format_check": screen["format_check"],
        "mbon_status": screen["mbon_status"],
        "oig_status": screen["oig_status"],
        "judiciary_status": screen["judiciary_status"],
        "credentialing_blocked": screen["blocked"],
        "message": _landing_apply_message(refreshed, screen),
        "portal_url": "/portal",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def _landing_apply_message(provider: MarylandProvider, screen: dict) -> str:
    if screen["blocked"]:
        return (
            "We received your application, but automated Maryland credentialing flagged an issue. "
            "Our compliance team will review your file before dispatching shifts."
        )
    if str(provider.license_status).upper() == "VERIFIED":
        return (
            "You're cleared for dispatch. Sign in to the clinician portal to enable push alerts "
            "and lock your first local per-diem shift."
        )
    return "Application received. Complete verification in the clinician portal."
