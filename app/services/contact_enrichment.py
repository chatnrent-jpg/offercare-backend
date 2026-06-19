"""Apollo / ZoomInfo contact enrichment for nursing home administrators."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass(frozen=True)
class EnrichedContact:
    full_name: str
    title: str
    email: str
    source: str


_DRY_RUN_DIRECTORY: dict[str, list[EnrichedContact]] = {
    "futurecare northpoint": [
        EnrichedContact(
            full_name="Patricia Hughes",
            title="Director of Nursing",
            email="phughes@futurecare.com",
            source="APOLLO_DRY_RUN",
        ),
        EnrichedContact(
            full_name="Michael Grant",
            title="Nursing Home Administrator",
            email="mgrant@futurecare.com",
            source="APOLLO_DRY_RUN",
        ),
    ],
    "genesis healthcare baltimore center": [
        EnrichedContact(
            full_name="Angela Brooks",
            title="Director of Nursing",
            email="abrooks@genesishealth.com",
            source="ZOOMINFO_DRY_RUN",
        ),
    ],
    "communicare silver spring": [
        EnrichedContact(
            full_name="Lisa Chen",
            title="Nursing Home Administrator",
            email="lchen@communicarehealth.com",
            source="APOLLO_DRY_RUN",
        ),
    ],
}


def _normalize_key(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _dry_run_contacts(facility_name: str) -> list[EnrichedContact]:
    key = _normalize_key(facility_name)
    if key in _DRY_RUN_DIRECTORY:
        return _DRY_RUN_DIRECTORY[key]
    token = key.replace(" ", ".")[:24] or "facility"
    return [
        EnrichedContact(
            full_name="Director of Nursing",
            title="Director of Nursing",
            email=f"don@{token}.md.demo",
            source="APOLLO_DRY_RUN",
        ),
        EnrichedContact(
            full_name="Nursing Home Administrator",
            title="Nursing Home Administrator",
            email=f"admin@{token}.md.demo",
            source="ZOOMINFO_DRY_RUN",
        ),
    ]


def _fetch_apollo_contacts(*, facility_name: str, city: str | None, state: str) -> list[EnrichedContact]:
    url = str(settings.APOLLO_SEARCH_URL or "").strip()
    api_key = str(settings.APOLLO_API_KEY or "").strip()
    if not url or not api_key:
        return []
    with httpx.Client(timeout=settings.CONTACT_ENRICH_TIMEOUT_SECONDS) as client:
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "organization_name": facility_name,
                "city": city,
                "state": state,
                "titles": ["Director of Nursing", "Nursing Home Administrator"],
            },
        )
        response.raise_for_status()
        payload = response.json()
    rows = payload.get("contacts") or []
    contacts: list[EnrichedContact] = []
    for row in rows:
        email = str(row.get("email") or "").strip()
        name = str(row.get("full_name") or row.get("name") or "").strip()
        if not email or not name:
            continue
        contacts.append(
            EnrichedContact(
                full_name=name,
                title=str(row.get("title") or "Administrator").strip(),
                email=email,
                source="APOLLO",
            )
        )
    return contacts


def _fetch_zoominfo_contacts(*, facility_name: str, city: str | None, state: str) -> list[EnrichedContact]:
    url = str(settings.ZOOMINFO_SEARCH_URL or "").strip()
    api_key = str(settings.ZOOMINFO_API_KEY or "").strip()
    if not url or not api_key:
        return []
    with httpx.Client(timeout=settings.CONTACT_ENRICH_TIMEOUT_SECONDS) as client:
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"company_name": facility_name, "city": city, "state": state},
        )
        response.raise_for_status()
        payload = response.json()
    rows = payload.get("contacts") or []
    contacts: list[EnrichedContact] = []
    for row in rows:
        email = str(row.get("email") or "").strip()
        name = str(row.get("full_name") or row.get("name") or "").strip()
        if not email or not name:
            continue
        contacts.append(
            EnrichedContact(
                full_name=name,
                title=str(row.get("title") or "Administrator").strip(),
                email=email,
                source="ZOOMINFO",
            )
        )
    return contacts


def enrich_facility_contacts(
    *,
    facility_name: str,
    city: str | None = None,
    state: str = "MD",
) -> list[EnrichedContact]:
    if settings.CONTACT_ENRICH_DRY_RUN:
        return _dry_run_contacts(facility_name)

    contacts: list[EnrichedContact] = []
    contacts.extend(_fetch_apollo_contacts(facility_name=facility_name, city=city, state=state))
    contacts.extend(_fetch_zoominfo_contacts(facility_name=facility_name, city=city, state=state))
    if not contacts:
        raise RuntimeError("No contacts returned — configure APOLLO_SEARCH_URL or ZOOMINFO_SEARCH_URL")
    return contacts
