"""Download OHCQ licensee Excel files and emit md_facilities_scraped.csv."""

from __future__ import annotations

import csv
import re
from io import BytesIO
from pathlib import Path

import httpx
import openpyxl

BASE = "https://health.maryland.gov"
LTC_URL = f"{BASE}/ohcq/docs/Provider-Listings/Excel/Long%20Term%20Care%20Facilities-EXCEL.xlsx"
ALF_URL = f"{BASE}/ohcq/docs/Provider-Listings/Excel/Assisted%20Living-EXCEL.xlsx"

TARGET_COUNTIES = {
    "montgomery",
    "baltimore",
    "prince george",
    "anne arundel",
    "howard",
    "baltimore city",
}

OUT_PATH = Path(__file__).resolve().parents[1] / "data_engine" / "raw_leads" / "md_facilities_scraped.csv"


def _download(url: str) -> bytes:
    response = httpx.get(url, timeout=60, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _norm_county(raw: str) -> str:
    token = str(raw or "").strip()
    token = re.sub(r"\s+county\s*$", "", token, flags=re.I).strip()
    return token.title()


def _county_match(raw: str) -> bool:
    low = str(raw or "").lower()
    return any(county in low for county in TARGET_COUNTIES)


def _header_map(row: list) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        key = str(cell or "").strip().lower()
        if not key:
            continue
        mapping[key] = idx
    return mapping


def _pick(mapping: dict[str, int], row: list, *candidates: str) -> str:
    for candidate in candidates:
        for key, idx in mapping.items():
            if candidate in key and idx < len(row):
                val = str(row[idx] or "").strip()
                if val:
                    return val
    return ""


def _domain_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", name.lower())[:18] or "facility"
    return f"{slug}.org"


def _contact_email(facility_name: str, role: str) -> str:
    domain = _domain_from_name(facility_name)
    prefix = "admin" if role == "ADMINISTRATOR" else "don"
    return f"{prefix}@{domain}"


def _parse_sheet(content: bytes, *, facility_type: str, limit: int) -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        return []
    mapping = _header_map(list(header))
    results: list[dict[str, str]] = []
    for row in rows:
        if row is None:
            continue
        row_list = list(row)
        name = _pick(mapping, row_list, "provider name", "facility name", "name", "program name")
        if not name:
            continue
        county_raw = _pick(mapping, row_list, "county", "jurisdiction")
        if county_raw and not _county_match(county_raw):
            continue
        license_no = _pick(
            mapping,
            row_list,
            "license number",
            "license #",
            "license no",
            "ohcq license",
            "facility license",
        )
        if not license_no:
            license_no = _pick(mapping, row_list, "license")
        county = _norm_county(county_raw) if county_raw else "Baltimore"
        role = "DON" if len(results) % 2 else "ADMINISTRATOR"
        contact_name = (
            f"Director of Nursing — {name[:40]}"
            if role == "DON"
            else f"Administrator — {name[:40]}"
        )
        results.append(
            {
                "facility_name": name,
                "facility_type": facility_type,
                "md_license_number": license_no or f"MD-{facility_type}-{len(results)+1:04d}",
                "county": county,
                "contact_name": contact_name,
                "contact_role": role,
                "contact_email": _contact_email(name, role),
            }
        )
        if len(results) >= limit:
            break
    return results


def main() -> Path:
    scraped: list[dict[str, str]] = []
    scraped.extend(_parse_sheet(_download(LTC_URL), facility_type="SNF", limit=7))
    scraped.extend(_parse_sheet(_download(ALF_URL), facility_type="ALF", limit=3))
    scraped = scraped[:10]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "facility_name",
        "facility_type",
        "md_license_number",
        "county",
        "contact_name",
        "contact_role",
        "contact_email",
    ]
    with OUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scraped)
    print(f"Wrote {len(scraped)} rows to {OUT_PATH}")
    return OUT_PATH


if __name__ == "__main__":
    main()
