"""Localized instant-pay landing pages — powered by route_manifest.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.schemas import BaltimoreInstantPayTextApplyRequest
from app.services.caregiver_intake_queue import queue_caregiver_text_intake
from app.services.maryland_landing import maryland_pay_bands
from app.services.worker_consent import WORKER_CONSENT_VERSION, build_consent_disclosures

_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "static" / "landing" / "route_manifest.py"
_manifest_module: Any | None = None


def _load_manifest_module() -> Any:
    global _manifest_module
    if _manifest_module is not None:
        return _manifest_module
    import sys

    module_name = "landing_route_manifest"
    spec = importlib.util.spec_from_file_location(module_name, _MANIFEST_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("landing_route_manifest_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _manifest_module = module
    return module


def get_route_manifest() -> Any:
    return _load_manifest_module()


def build_localized_instant_pay_page(region_slug: str, license_slug: str) -> dict[str, Any]:
    manifest = get_route_manifest()
    route = manifest.resolve_route_parts(region_slug, license_slug)
    disclosures = build_consent_disclosures()
    bands = {band.credential_type: band for band in maryland_pay_bands()}
    band = bands.get(route.license.credential_type) or bands.get("CNA")
    typical_pay = float(band.typical_hourly_pay if band else 24.0)

    region_meta = manifest.region_metadata_payload(route)
    return {
        "slug": route.landing_slug,
        "path": route.path,
        "region_slug": route.region_slug,
        "license_slug": route.license_slug,
        "market": route.region.market,
        "region_label": route.region.label,
        "county": route.region.county,
        "credential_type": route.license.credential_type,
        "license_label": route.license.label,
        "headline": (
            f"{route.region.label} {route.license.headline_role} shifts — "
            "get paid the moment your shift ends"
        ),
        "subheadline": (
            f"W-2 {route.license.label} floor staff in {route.region.county} County with automated "
            "Maryland tax withholding and Stripe instant payout after supervisor sign-off."
        ),
        "selling_points": [
            {
                "id": "instant_stripe_payout",
                "title": "Instant shift payout",
                "badge": "Stripe bridge",
                "body": (
                    "When your timesheet is signed, our payroll tax intercept bridge calculates "
                    "Maryland W-2 withholdings and routes net pay through Stripe instant payout — "
                    "typically within 30 minutes of shift completion."
                ),
                "icon": "zap",
            },
            {
                "id": "w2_compliance",
                "title": "Automated W-2 compliance",
                "badge": "Tier 1 W-2",
                "body": (
                    "You are a W-2 employee — not a 1099 contractor. Federal FICA, Maryland state tax, "
                    "and county piggyback withholding run automatically before any payout hits your account."
                ),
                "icon": "shield",
            },
        ],
        "trust_chips": [
            "MBON-verified before dispatch",
            f"{route.region.label} SNF & ALF coverage",
            "Text-to-apply in 30 seconds",
        ],
        "typical_hourly_pay": typical_pay,
        "apply_defaults": {
            "credential_type": route.license.credential_type,
            "state": "MD",
            "market": route.region.market,
            "region_slug": route.region_slug,
            "license_slug": route.license_slug,
            "default_zip": route.region.default_zip,
            "service_lines": "NURSING_HOME",
        },
        "text_apply": {
            "headline": f"Text to apply — {route.region.label} {route.license.label} shifts",
            "subheadline": (
                "Enter your mobile number. Our intake team texts you a 2-minute onboarding link."
            ),
            "cta_label": "Text me shift offers",
            "phone_placeholder": route.region.phone_placeholder,
            "consent_label": disclosures["sms_dispatch"],
        },
        "consent_version": WORKER_CONSENT_VERSION,
        "full_apply_url": "/join",
        "portal_url": "/portal",
        "layout": manifest.V0_LAYOUT_RULES,
        "api_path": route.api_path,
        "text_apply_api_path": route.text_apply_api_path,
        "intake_table": route.intake_table,
        "region_metadata": region_meta,
    }


def queue_localized_text_apply(
    db: Session,
    region_slug: str,
    license_slug: str,
    payload: BaltimoreInstantPayTextApplyRequest,
    *,
    client_ip: str | None = None,
) -> dict:
    manifest = get_route_manifest()
    route = manifest.resolve_route_parts(region_slug, license_slug)
    region_meta = manifest.region_metadata_payload(route)

    result = queue_caregiver_text_intake(
        db,
        phone_number=payload.phone_number,
        landing_slug=route.landing_slug,
        market=route.region.market,
        credential_type=route.license.credential_type,
        full_name=payload.full_name,
        home_zip=payload.home_zip or route.region.default_zip,
        consent_version=payload.consent_version,
        sms_consent=payload.consent_sms_dispatch,
        client_ip=client_ip,
        notes=f"text-to-apply:{route.landing_slug}",
        source_channel=f"landing:{route.region_slug}:{route.license_slug}",
        region_metadata=region_meta,
    )
    return {
        **result,
        "region_metadata": region_meta,
        "message": (
            f"You're in the {route.region.label} {route.license.label} intake queue. "
            "Watch for a text with your onboarding link and first instant-pay shift offer."
        ),
        "full_apply_url": "/join",
    }


def export_route_manifest() -> dict[str, Any]:
    return get_route_manifest().manifest_export()
