"""Maryland OHCQ + CMS staffing citation sweep — flags SNF/ALF staffing deficits."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

import httpx
import openpyxl

from data_engine.md_county_normalizer import normalize_md_county
from data_engine.paths import LEADS_DIR, ensure_data_engine_dirs

logger = logging.getLogger(__name__)

MDH_BASE = "https://health.maryland.gov"
OHCQ_HOME = f"{MDH_BASE}/ohcq/Pages/home.aspx"
OHCQ_DIRECTORIES = f"{MDH_BASE}/ohcq/Pages/OHCQ-Licensee-Directories.aspx"
LTC_EXCEL = f"{MDH_BASE}/ohcq/docs/Provider-Listings/Excel/Long%20Term%20Care%20Facilities-EXCEL.xlsx"
ALF_EXCEL = f"{MDH_BASE}/ohcq/docs/Provider-Listings/Excel/Assisted%20Living-EXCEL.xlsx"

CMS_NH_PROVIDER_API = "https://data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py/0"
CMS_NH_CITATIONS_API = "https://data.cms.gov/provider-data/api/1/datastore/query/r5ix-sfxw/0"

DEFAULT_OUTPUT = LEADS_DIR / "ohcq_staffing_citation_flags_md.csv"

# Maryland nursing-home minimum direct-care hours (HPRD) — COMAR / state staffing mandates.
MD_SNFF_MIN_HPRD = 3.76

STAFFING_CITATION_TAGS = frozenset({"0725", "725", "0726", "726", "0727", "727", "0728", "728"})
STAFFING_KEYWORDS = (
    "insufficient staffing",
    "staffing shortage",
    "sufficient number of",
    "nurse staffing",
    "licensed nurse",
    "staffing levels",
    "personnel to meet",
    "hours per resident",
)

OHCQ_PORTAL_PAGES = (
    OHCQ_HOME,
    OHCQ_DIRECTORIES,
    f"{MDH_BASE}/ohcq/Pages/Long-Term-Care.aspx",
    f"{MDH_BASE}/ohcq/Pages/Assisted-Living-Programs.aspx",
    f"{MDH_BASE}/ohcq/Pages/File-a-Complaint.aspx",
)

CSV_FIELDS = (
    "facility_name",
    "county",
    "facility_type",
    "flag_reason",
    "deficiency_tag",
    "deficiency_summary",
    "survey_date",
    "reported_nurse_hprd",
    "state_mandated_hprd",
    "casemix_expected_hprd",
    "staffing_rating",
    "md_license_number",
    "cms_ccn",
    "source_portal",
    "source_url",
    "scraped_at_utc",
)


@dataclass(frozen=True)
class FacilityRegistryRow:
    facility_name: str
    facility_type: str
    county: str
    md_license_number: str


@dataclass(frozen=True)
class StaffingFlagRow:
    facility_name: str
    county: str
    facility_type: str
    flag_reason: str
    deficiency_tag: str = ""
    deficiency_summary: str = ""
    survey_date: str = ""
    reported_nurse_hprd: str = ""
    state_mandated_hprd: str = ""
    casemix_expected_hprd: str = ""
    staffing_rating: str = ""
    md_license_number: str = ""
    cms_ccn: str = ""
    source_portal: str = "OHCQ+CMS"
    source_url: str = ""
    scraped_at_utc: str = ""

    def as_csv_row(self) -> dict[str, str]:
        return {field: str(getattr(self, field) or "") for field in CSV_FIELDS}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_name(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\s+", " ", token)


def _norm_county(raw: str) -> str:
    return normalize_md_county(raw).normalized or "Unknown"


def _download(client: httpx.Client, url: str) -> bytes:
    response = client.get(url, timeout=90, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _header_map(row: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        key = str(cell or "").strip().lower()
        if key:
            mapping[key] = idx
    return mapping


def _pick(mapping: dict[str, int], row: list[Any], *candidates: str) -> str:
    for candidate in candidates:
        for key, idx in mapping.items():
            if candidate in key and idx < len(row):
                val = str(row[idx] or "").strip()
                if val:
                    return val
    return ""


def parse_ohcq_excel(content: bytes, *, facility_type: str) -> list[FacilityRegistryRow]:
    workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        return []

    mapping = _header_map(list(header))
    parsed: list[FacilityRegistryRow] = []
    for row in rows:
        if row is None:
            continue
        row_list = list(row)
        name = _pick(mapping, row_list, "provider name", "facility name", "name", "program name")
        if not name:
            continue
        county_raw = _pick(mapping, row_list, "county", "jurisdiction")
        license_no = _pick(
            mapping,
            row_list,
            "license number",
            "license #",
            "license no",
            "ohcq license",
            "facility license",
            "license",
        )
        parsed.append(
            FacilityRegistryRow(
                facility_name=name.strip(),
                facility_type=facility_type,
                county=_norm_county(county_raw) if county_raw else "Unknown",
                md_license_number=license_no.strip(),
            )
        )
    return parsed


def load_ohcq_facility_registry(client: httpx.Client) -> list[FacilityRegistryRow]:
    registry: list[FacilityRegistryRow] = []
    registry.extend(parse_ohcq_excel(_download(client, LTC_EXCEL), facility_type="SNF"))
    registry.extend(parse_ohcq_excel(_download(client, ALF_EXCEL), facility_type="ALF"))
    logger.info("OHCQ registry loaded: %s facilities", len(registry))
    return registry


def sweep_ohcq_portal_links(client: httpx.Client) -> list[str]:
    """Crawl MDH OHCQ portal pages and collect survey/citation document links."""
    discovered: list[str] = []
    link_pattern = re.compile(r'href="([^"]+)"', re.I)
    keywords = ("citation", "defici", "survey", "staff", "enforce", "complaint", "excel", "xlsx", "pdf")
    for page_url in OHCQ_PORTAL_PAGES:
        try:
            response = client.get(page_url, timeout=45, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.debug("OHCQ portal page not found (skipped): %s", page_url)
            else:
                logger.warning("OHCQ portal fetch failed url=%s error=%s", page_url, exc)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("OHCQ portal fetch failed url=%s error=%s", page_url, exc)
            continue
        for match in link_pattern.findall(response.text):
            href = match.strip()
            if not href or href.startswith("#"):
                continue
            low = href.lower()
            if not any(keyword in low for keyword in keywords):
                continue
            if href.startswith("/"):
                href = f"{MDH_BASE}{href}"
            elif not href.startswith("http"):
                continue
            discovered.append(href)
    unique = sorted(set(discovered))
    logger.info("OHCQ portal sweep discovered %s document links", len(unique))
    return unique


def _fetch_cms_dataset(
    client: httpx.Client,
    *,
    api_url: str,
    state: str = "MD",
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    conditions = [{"property": "state", "value": state.upper(), "operator": "="}]
    offset = 0
    rows: list[dict[str, Any]] = []
    while True:
        body = {"conditions": conditions, "limit": page_size, "offset": offset}
        response = client.post(api_url, json=body, timeout=120)
        response.raise_for_status()
        batch = response.json().get("results") or []
        if not isinstance(batch, list):
            raise ValueError("unexpected_cms_payload")
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _safe_float(value: Any) -> float | None:
    token = str(value or "").strip()
    if not token or token.lower() in {"na", "n/a", "-", ""}:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _is_staffing_citation(row: dict[str, Any]) -> bool:
    tag = str(row.get("deficiency_tag_number") or "").strip()
    if tag in STAFFING_CITATION_TAGS:
        return True
    category = str(row.get("deficiency_category") or "").lower()
    if "nursing and physician services" in category:
        return True
    blob = " ".join(
        [
            str(row.get("deficiency_description") or "").lower(),
            category,
        ]
    )
    return any(keyword in blob for keyword in STAFFING_KEYWORDS)


def _registry_lookup(registry: list[FacilityRegistryRow]) -> dict[str, FacilityRegistryRow]:
    by_name: dict[str, FacilityRegistryRow] = {}
    by_license: dict[str, FacilityRegistryRow] = {}
    for row in registry:
        by_name[_norm_name(row.facility_name)] = row
        if row.md_license_number:
            by_license[row.md_license_number.upper()] = row
    return {"name": by_name, "license": by_license}


def _resolve_registry_row(
    *,
    facility_name: str,
    registry_index: dict[str, dict[str, FacilityRegistryRow]],
    md_license_number: str = "",
) -> FacilityRegistryRow | None:
    license_key = str(md_license_number or "").strip().upper()
    if license_key and license_key in registry_index["license"]:
        return registry_index["license"][license_key]
    name_key = _norm_name(facility_name)
    if name_key in registry_index["name"]:
        return registry_index["name"][name_key]
    for norm, row in registry_index["name"].items():
        if name_key and (name_key in norm or norm in name_key):
            return row
    return None


def flags_from_cms_staffing_citations(
    citations: Iterable[dict[str, Any]],
    *,
    registry_index: dict[str, dict[str, FacilityRegistryRow]],
    scraped_at: str,
) -> list[StaffingFlagRow]:
    flags: list[StaffingFlagRow] = []
    seen: set[tuple[str, str, str]] = set()
    for row in citations:
        if not _is_staffing_citation(row):
            continue
        facility_name = str(row.get("provider_name") or "").strip()
        if not facility_name:
            continue
        dedupe_key = (
            _norm_name(facility_name),
            str(row.get("deficiency_tag_number") or ""),
            str(row.get("survey_date") or ""),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        registry_row = _resolve_registry_row(facility_name=facility_name, registry_index=registry_index)
        county = registry_row.county if registry_row else _norm_county(str(row.get("citytown") or "Unknown"))
        facility_type = registry_row.facility_type if registry_row else "SNF"
        license_no = registry_row.md_license_number if registry_row else ""

        flags.append(
            StaffingFlagRow(
                facility_name=facility_name,
                county=county,
                facility_type=facility_type,
                flag_reason="insufficient_staffing_citation",
                deficiency_tag=str(row.get("deficiency_tag_number") or ""),
                deficiency_summary=str(row.get("deficiency_description") or "")[:500],
                survey_date=str(row.get("survey_date") or ""),
                md_license_number=license_no,
                cms_ccn=str(row.get("cms_certification_number_ccn") or ""),
                source_portal="CMS_HEALTH_CITATIONS",
                source_url=CMS_NH_CITATIONS_API,
                scraped_at_utc=scraped_at,
            )
        )
    return flags


def flags_from_cms_below_mandated_hours(
    providers: Iterable[dict[str, Any]],
    *,
    registry_index: dict[str, dict[str, FacilityRegistryRow]],
    scraped_at: str,
    min_hprd: float = MD_SNFF_MIN_HPRD,
) -> list[StaffingFlagRow]:
    flags: list[StaffingFlagRow] = []
    seen: set[str] = set()
    for row in providers:
        facility_name = str(row.get("provider_name") or "").strip()
        if not facility_name:
            continue
        reported = _safe_float(row.get("reported_total_nurse_staffing_hours_per_resident_per_day"))
        casemix = _safe_float(row.get("casemix_total_nurse_staffing_hours_per_resident_per_day"))
        staffing_rating = _safe_float(row.get("staffing_rating"))

        below_state = reported is not None and reported < min_hprd
        below_casemix = reported is not None and casemix is not None and reported < casemix
        low_star = staffing_rating is not None and staffing_rating <= 2
        if not (below_state or below_casemix or low_star):
            continue

        name_key = _norm_name(facility_name)
        if name_key in seen:
            continue
        seen.add(name_key)

        registry_row = _resolve_registry_row(facility_name=facility_name, registry_index=registry_index)
        county = _norm_county(str(row.get("countyparish") or ""))
        if registry_row:
            county = registry_row.county
        facility_type = registry_row.facility_type if registry_row else "SNF"
        license_no = registry_row.md_license_number if registry_row else ""

        if below_state:
            reason = "below_state_mandated_care_hours"
        elif below_casemix:
            reason = "below_casemix_expected_care_hours"
        else:
            reason = "low_staffing_rating"

        reported_token = f"{reported:.3f}" if reported is not None else "n/a"
        casemix_token = f"{casemix:.3f}" if casemix is not None else "n/a"
        rating_token = str(int(staffing_rating)) if staffing_rating is not None else "n/a"

        flags.append(
            StaffingFlagRow(
                facility_name=facility_name,
                county=county,
                facility_type=facility_type,
                flag_reason=reason,
                deficiency_summary=(
                    f"Reported nurse HPRD {reported_token}; state minimum {min_hprd:.2f}; "
                    f"casemix expected {casemix_token}; staffing rating {rating_token}."
                ),
                reported_nurse_hprd=f"{reported:.5f}" if reported is not None else "",
                state_mandated_hprd=f"{min_hprd:.2f}",
                casemix_expected_hprd=f"{casemix:.5f}" if casemix is not None else "",
                staffing_rating=str(int(staffing_rating)) if staffing_rating is not None else "",
                md_license_number=license_no,
                cms_ccn=str(row.get("cms_certification_number_ccn") or ""),
                source_portal="CMS_NH_PROVIDER_INFO",
                source_url=CMS_NH_PROVIDER_API,
                scraped_at_utc=scraped_at,
            )
        )
    return flags


def merge_staffing_flags(*groups: Iterable[StaffingFlagRow]) -> list[StaffingFlagRow]:
    merged: list[StaffingFlagRow] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for row in group:
            key = (_norm_name(row.facility_name), row.county.lower(), row.flag_reason)
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    merged.sort(key=lambda item: (item.county.lower(), item.facility_name.lower(), item.flag_reason))
    return merged


def write_staffing_flags_csv(rows: Iterable[StaffingFlagRow], output_path: Path | None = None) -> Path:
    ensure_data_engine_dirs()
    destination = output_path or DEFAULT_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(rows)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        for row in materialized:
            writer.writerow(row.as_csv_row())
    logger.info("Wrote %s staffing flags to %s", len(materialized), destination)
    return destination


def run_ohcq_staffing_citation_sweep(
    *,
    output_path: Path | None = None,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Sweep OHCQ portals + CMS mirrors; emit flagged facilities CSV under /leads."""
    scraped_at = _utc_now_iso()
    if dry_run:
        sample = [
            StaffingFlagRow(
                facility_name="Sample SNF — Insufficient Staffing",
                county="Montgomery",
                facility_type="SNF",
                flag_reason="insufficient_staffing_citation",
                deficiency_tag="0725",
                deficiency_summary="Dry-run sample — sufficient nursing staff citation.",
                survey_date="2026-01-15",
                md_license_number="MD-SNF-0001",
                source_portal="OHCQ+CMS",
                source_url=OHCQ_DIRECTORIES,
                scraped_at_utc=scraped_at,
            ),
            StaffingFlagRow(
                facility_name="Sample ALF — Below Care Hours",
                county="Baltimore",
                facility_type="ALF",
                flag_reason="below_state_mandated_care_hours",
                reported_nurse_hprd="2.85000",
                state_mandated_hprd=f"{MD_SNFF_MIN_HPRD:.2f}",
                source_portal="OHCQ+CMS",
                source_url=ALF_EXCEL,
                scraped_at_utc=scraped_at,
            ),
        ]
        csv_path = write_staffing_flags_csv(sample, output_path)
        return {
            "ok": True,
            "dry_run": True,
            "flag_count": len(sample),
            "output_csv": str(csv_path),
            "ohcq_portal_links_discovered": 0,
            "registry_facilities": 0,
            "cms_citations_scanned": 0,
            "cms_providers_scanned": 0,
        }

    owns_client = client is None
    http = client or httpx.Client(headers={"User-Agent": "VettedMe-OHCQ-CitationTracker/1.0"})
    try:
        portal_links = sweep_ohcq_portal_links(http)
        registry = load_ohcq_facility_registry(http)
        registry_index = _registry_lookup(registry)

        citations = _fetch_cms_dataset(http, api_url=CMS_NH_CITATIONS_API)
        providers = _fetch_cms_dataset(http, api_url=CMS_NH_PROVIDER_API)

        citation_flags = flags_from_cms_staffing_citations(
            citations,
            registry_index=registry_index,
            scraped_at=scraped_at,
        )
        hours_flags = flags_from_cms_below_mandated_hours(
            providers,
            registry_index=registry_index,
            scraped_at=scraped_at,
        )
        merged = merge_staffing_flags(citation_flags, hours_flags)
        csv_path = write_staffing_flags_csv(merged, output_path)
        return {
            "ok": True,
            "dry_run": False,
            "flag_count": len(merged),
            "output_csv": str(csv_path),
            "ohcq_portal_links_discovered": len(portal_links),
            "registry_facilities": len(registry),
            "cms_citations_scanned": len(citations),
            "cms_providers_scanned": len(providers),
            "citation_flags": len(citation_flags),
            "hours_flags": len(hours_flags),
            "ohcq_portal_links": portal_links[:25],
        }
    finally:
        if owns_client:
            http.close()
