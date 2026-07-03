"""Programmatic routing configuration — localized instant-pay landing URL generation.

Supports variable URLs from Maryland Region × License Type parameters.
All routes share the v0-optimized instant-pay layout and map to caregiver_intake_queue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class MarylandRegionSpec:
    slug: str
    label: str
    market: str
    county: str
    default_zip: str
    phone_placeholder: str
    service_radius_miles: int = 35


@dataclass(frozen=True)
class LicenseTypeSpec:
    slug: str
    credential_type: str
    label: str
    headline_role: str


@dataclass(frozen=True)
class LocalizedRouteSpec:
    region_slug: str
    license_slug: str
    landing_slug: str
    path: str
    api_path: str
    text_apply_api_path: str
    region: MarylandRegionSpec
    license: LicenseTypeSpec
    layout_template: str
    intake_table: str = "caregiver_intake_queue"


# v0 layout rules — shared CSS/JS/HTML shell (mobile-first conversion layout)
V0_LAYOUT_RULES: dict[str, Any] = {
    "template_dir": "baltimore-instant-pay-cna",
    "static_mount_pattern": "/{landing_slug}",
    "stylesheet": "/{landing_slug}/styles.css",
    "script": "/{landing_slug}/app.js",
    "theme_color": "#059669",
    "font_family": "Inter",
    "layout_profile": "v0-mobile-first-instant-pay",
    "conversion_blocks": [
        "sticky_top_bar",
        "hero_with_trust_chips",
        "dual_selling_point_cards",
        "text_to_apply_form",
        "sticky_bottom_cta",
    ],
    "selling_points": ["instant_stripe_payout", "w2_compliance"],
}

MARYLAND_REGIONS: dict[str, MarylandRegionSpec] = {
    "baltimore": MarylandRegionSpec(
        slug="baltimore",
        label="Baltimore",
        market="Baltimore",
        county="Baltimore City",
        default_zip="21201",
        phone_placeholder="(410) 555-0199",
    ),
    "silver-spring": MarylandRegionSpec(
        slug="silver-spring",
        label="Silver Spring",
        market="Silver Spring",
        county="Montgomery",
        default_zip="20910",
        phone_placeholder="(301) 555-0199",
    ),
    "bethesda": MarylandRegionSpec(
        slug="bethesda",
        label="Bethesda",
        market="Bethesda",
        county="Montgomery",
        default_zip="20814",
        phone_placeholder="(301) 555-0142",
    ),
}

LICENSE_TYPES: dict[str, LicenseTypeSpec] = {
    "cna": LicenseTypeSpec(
        slug="cna",
        credential_type="CNA",
        label="CNA",
        headline_role="CNA",
    ),
    "gna": LicenseTypeSpec(
        slug="gna",
        credential_type="GNA",
        label="GNA",
        headline_role="GNA",
    ),
    "lpn": LicenseTypeSpec(
        slug="lpn",
        credential_type="LPN",
        label="LPN",
        headline_role="LPN",
    ),
}


def build_landing_slug(region_slug: str, license_slug: str) -> str:
    region = normalize_region_slug(region_slug)
    license_type = normalize_license_slug(license_slug)
    return f"{region}-instant-pay-{license_type}"


def build_path(region_slug: str, license_slug: str) -> str:
    return f"/{build_landing_slug(region_slug, license_slug)}/"


def normalize_region_slug(value: str) -> str:
    token = str(value or "").strip().lower().replace("_", "-")
    if token not in MARYLAND_REGIONS:
        raise ValueError("unsupported_region")
    return token


def normalize_license_slug(value: str) -> str:
    token = str(value or "").strip().lower()
    if token not in LICENSE_TYPES:
        raise ValueError("unsupported_license_type")
    return token


def resolve_route(landing_slug: str) -> LocalizedRouteSpec:
    token = str(landing_slug or "").strip().lower().strip("/")
    for route in iter_routes():
        if route.landing_slug == token:
            return route
    raise ValueError("unknown_landing_route")


def resolve_route_parts(region_slug: str, license_slug: str) -> LocalizedRouteSpec:
    region = normalize_region_slug(region_slug)
    license_type = normalize_license_slug(license_slug)
    landing_slug = build_landing_slug(region, license_type)
    return LocalizedRouteSpec(
        region_slug=region,
        license_slug=license_type,
        landing_slug=landing_slug,
        path=build_path(region, license_type),
        api_path=f"/api/landing/instant-pay/{region}/{license_type}",
        text_apply_api_path=f"/api/landing/instant-pay/{region}/{license_type}/text-apply",
        region=MARYLAND_REGIONS[region],
        license=LICENSE_TYPES[license_type],
        layout_template=V0_LAYOUT_RULES["template_dir"],
    )


def iter_routes(
    *,
    regions: list[str] | None = None,
    licenses: list[str] | None = None,
) -> Iterator[LocalizedRouteSpec]:
    region_slugs = regions or list(MARYLAND_REGIONS.keys())
    license_slugs = licenses or list(LICENSE_TYPES.keys())
    for region_slug in region_slugs:
        for license_slug in license_slugs:
            yield resolve_route_parts(region_slug, license_slug)


def region_metadata_payload(route: LocalizedRouteSpec) -> dict[str, Any]:
    """Metadata passed through to caregiver_intake_queue onboarding payload."""
    return {
        "region_slug": route.region_slug,
        "region_label": route.region.label,
        "market": route.region.market,
        "county": route.region.county,
        "default_zip": route.region.default_zip,
        "license_slug": route.license_slug,
        "credential_type": route.license.credential_type,
        "license_label": route.license.label,
        "landing_slug": route.landing_slug,
        "layout_profile": V0_LAYOUT_RULES["layout_profile"],
        "service_radius_miles": route.region.service_radius_miles,
    }


def manifest_export() -> dict[str, Any]:
    routes = [route.__dict__ | {"region_metadata": region_metadata_payload(route)} for route in iter_routes()]
    return {
        "manifest_version": "2026-07-02",
        "intake_table": "caregiver_intake_queue",
        "url_pattern": "{region}-instant-pay-{license}",
        "v0_layout_rules": V0_LAYOUT_RULES,
        "regions": {key: spec.__dict__ for key, spec in MARYLAND_REGIONS.items()},
        "license_types": {key: spec.__dict__ for key, spec in LICENSE_TYPES.items()},
        "routes": [
            {
                "landing_slug": r.landing_slug,
                "path": r.path,
                "api_path": r.api_path,
                "text_apply_api_path": r.text_apply_api_path,
                "region_slug": r.region_slug,
                "license_slug": r.license_slug,
                "layout_template": r.layout_template,
                "intake_table": r.intake_table,
                "region_metadata": region_metadata_payload(r),
            }
            for r in iter_routes()
        ],
        "route_count": len(routes),
    }
