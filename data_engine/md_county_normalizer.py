"""Normalize Maryland county names — CMS city tokens → official county for outreach copy."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Maryland's 23 counties + Baltimore City (independent city).
MD_OFFICIAL_COUNTIES: frozenset[str] = frozenset(
    {
        "Allegany",
        "Anne Arundel",
        "Baltimore",
        "Baltimore City",
        "Calvert",
        "Caroline",
        "Carroll",
        "Cecil",
        "Charles",
        "Dorchester",
        "Frederick",
        "Garrett",
        "Harford",
        "Howard",
        "Kent",
        "Montgomery",
        "Prince George's",
        "Queen Anne's",
        "Somerset",
        "St. Mary's",
        "Talbot",
        "Washington",
        "Wicomico",
        "Worcester",
    }
)

# CMS/OHCQ often emit municipality names in the county column when registry lookup misses.
MD_CITY_TO_COUNTY: dict[str, str] = {
    "adamstown": "Frederick",
    "adelphi": "Prince George's",
    "annapolis": "Anne Arundel",
    "arnold": "Anne Arundel",
    "baltimore": "Baltimore",
    "bel air": "Harford",
    "beltsville": "Prince George's",
    "bethesda": "Montgomery",
    "bowie": "Prince George's",
    "catonsville": "Baltimore",
    "cheverly": "Prince George's",
    "chestertown": "Kent",
    "clinton": "Prince George's",
    "cockeysville": "Baltimore",
    "college park": "Prince George's",
    "columbia": "Howard",
    "crofton": "Anne Arundel",
    "cumberland": "Allegany",
    "easton": "Talbot",
    "elkton": "Cecil",
    "ellicott city": "Howard",
    "frederick": "Frederick",
    "gaithersburg": "Montgomery",
    "germantown": "Montgomery",
    "glen burnie": "Anne Arundel",
    "hagerstown": "Washington",
    "hyattsville": "Prince George's",
    "laurel": "Prince George's",
    "lexington park": "St. Mary's",
    "ocean city": "Worcester",
    "owings mills": "Baltimore",
    "pasadena": "Anne Arundel",
    "pikesville": "Baltimore",
    "rockville": "Montgomery",
    "salisbury": "Wicomico",
    "severna park": "Anne Arundel",
    "silver spring": "Montgomery",
    "towson": "Baltimore",
    "upper marlboro": "Prince George's",
    "waldorf": "Charles",
    "westminster": "Carroll",
}


@dataclass(frozen=True)
class CountyNormalization:
    raw: str
    normalized: str
    verified: bool
    source: str  # official | city_map | passthrough


def _canonical_key(value: str) -> str:
    token = str(value or "").strip().lower()
    token = re.sub(r"\s+county\s*$", "", token)
    token = re.sub(r"\s+", " ", token)
    return token


def _title_county(value: str) -> str:
    token = str(value or "").strip()
    token = re.sub(r"\s+county\s*$", "", token, flags=re.I).strip()
    if token.lower() == "baltimore city":
        return "Baltimore City"
    if token.lower() == "prince georges":
        return "Prince George's"
    if token.lower() in {"st marys", "st. marys"}:
        return "St. Mary's"
    if token.lower() in {"queen annes", "queen anne's"}:
        return "Queen Anne's"
    return token.title()


def normalize_md_county(raw: str) -> CountyNormalization:
    """Return canonical Maryland county when possible."""
    raw_token = str(raw or "").strip()
    if not raw_token:
        return CountyNormalization(raw="", normalized="", verified=False, source="passthrough")

    key = _canonical_key(raw_token)
    titled = _title_county(raw_token)

    if titled in MD_OFFICIAL_COUNTIES:
        return CountyNormalization(raw=raw_token, normalized=titled, verified=True, source="official")

    mapped = MD_CITY_TO_COUNTY.get(key)
    if mapped:
        return CountyNormalization(raw=raw_token, normalized=mapped, verified=True, source="city_map")

    return CountyNormalization(raw=raw_token, normalized=titled, verified=False, source="passthrough")
