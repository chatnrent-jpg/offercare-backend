"""Care settings, shift roles, and clinician credential taxonomy."""

from __future__ import annotations

import re

FACILITY_TYPES: tuple[str, ...] = (
    "HOSPITAL",
    "NURSING_HOME",
    "HOME_HEALTH",
    "URGENT_CARE",
    "HEALTHCARE",
)

CREDENTIAL_TYPES: tuple[str, ...] = (
    "RN",
    "LPN",
    "CNA",
    "GNA",
    "NA",
)

SHIFT_ROLES: tuple[str, ...] = (
    "ICU_RN",
    "ER_RN",
    "MED_SURG_RN",
    "HOME_HEALTH_RN",
    "LPN",
    "CNA",
    "GNA",
    "NURSING_ASSISTANT",
    "URGENT_RN",
)

FACILITY_TYPE_LABELS: dict[str, str] = {
    "HOSPITAL": "Hospital",
    "NURSING_HOME": "Nursing home / SNF",
    "HOME_HEALTH": "Home health",
    "URGENT_CARE": "Urgent care",
    "HEALTHCARE": "Healthcare facility",
}

CREDENTIAL_LABELS: dict[str, str] = {
    "RN": "Registered Nurse (RN)",
    "LPN": "Licensed Practical Nurse (LPN)",
    "CNA": "Certified Nursing Assistant (CNA)",
    "GNA": "Geriatric Nursing Assistant (GNA)",
    "NA": "Nursing Assistant",
}

SHIFT_ROLE_LABELS: dict[str, str] = {
    "ICU_RN": "ICU RN",
    "ER_RN": "Emergency RN",
    "MED_SURG_RN": "Med-Surg RN",
    "HOME_HEALTH_RN": "Home health RN",
    "LPN": "LPN",
    "CNA": "CNA",
    "GNA": "GNA",
    "NURSING_ASSISTANT": "Nursing assistant",
    "URGENT_RN": "Urgent care RN",
}

SHIFT_TEMPLATES_BY_FACILITY_TYPE: dict[str, tuple[tuple[str, float], ...]] = {
    "HOSPITAL": (
        ("ICU_RN", 120.0),
        ("ER_RN", 110.0),
        ("MED_SURG_RN", 95.0),
    ),
    "NURSING_HOME": (
        ("LPN", 42.0),
        ("CNA", 22.0),
        ("GNA", 24.0),
        ("NURSING_ASSISTANT", 20.0),
    ),
    "HOME_HEALTH": (
        ("HOME_HEALTH_RN", 55.0),
        ("LPN", 38.0),
        ("CNA", 21.0),
    ),
    "URGENT_CARE": (("URGENT_RN", 85.0),),
    "HEALTHCARE": (
        ("LPN", 40.0),
        ("CNA", 22.0),
        ("NURSING_ASSISTANT", 20.0),
    ),
}

ROLE_CREDENTIAL_MAP: dict[str, tuple[str, ...]] = {
    "ICU_RN": ("RN",),
    "ER_RN": ("RN",),
    "MED_SURG_RN": ("RN",),
    "HOME_HEALTH_RN": ("RN",),
    "URGENT_RN": ("RN",),
    "LPN": ("LPN",),
    "CNA": ("CNA", "GNA", "NA"),
    "GNA": ("GNA", "CNA"),
    "NURSING_ASSISTANT": ("NA", "CNA", "GNA"),
}

NON_NPI_CREDENTIALS: frozenset[str] = frozenset({"CNA", "GNA", "NA"})

# Maryland and DC license GNAs as a distinct credential; other Mid-Atlantic states use CNA.
GNA_LICENSE_STATES: frozenset[str] = frozenset({"MD", "DC"})


def normalize_token(value: str, allowed: tuple[str, ...], *, fallback: str) -> str:
    token = re.sub(r"[^A-Z0-9_]", "_", str(value or "").strip().upper())
    token = re.sub(r"_+", "_", token).strip("_")
    if token in allowed:
        return token
    aliases = {
        "REGISTERED_NURSE": "RN",
        "LICENSED_PRACTICAL_NURSE": "LPN",
        "CERTIFIED_NURSING_ASSISTANT": "CNA",
        "GERIATRIC_NURSING_ASSISTANT": "GNA",
        "NURSING_ASSISTANT": "NA",
        "SNF": "NURSING_HOME",
        "SKILLED_NURSING": "NURSING_HOME",
        "HOME_CARE": "HOME_HEALTH",
    }
    if token in aliases:
        mapped = aliases[token]
        if mapped in allowed:
            return mapped
    return fallback


def normalize_facility_type(value: str) -> str:
    return normalize_token(value, FACILITY_TYPES, fallback="HEALTHCARE")


def normalize_credential_type(value: str) -> str:
    return normalize_token(value, CREDENTIAL_TYPES, fallback="RN")


def normalize_shift_role(value: str) -> str:
    return normalize_token(value, SHIFT_ROLES, fallback="MED_SURG_RN")


def facility_type_label(value: str) -> str:
    return FACILITY_TYPE_LABELS.get(normalize_facility_type(value), str(value))


def credential_label(value: str) -> str:
    return CREDENTIAL_LABELS.get(normalize_credential_type(value), str(value))


def shift_role_label(value: str) -> str:
    return SHIFT_ROLE_LABELS.get(normalize_shift_role(value), str(value))


def shift_templates_for_facility_type(facility_type: str) -> tuple[tuple[str, float], ...]:
    return SHIFT_TEMPLATES_BY_FACILITY_TYPE.get(
        normalize_facility_type(facility_type),
        SHIFT_TEMPLATES_BY_FACILITY_TYPE["HEALTHCARE"],
    )


def credential_types_for_state(state: str) -> tuple[str, ...]:
    if normalize_state(state) in GNA_LICENSE_STATES:
        return CREDENTIAL_TYPES
    return tuple(code for code in CREDENTIAL_TYPES if code != "GNA")


def credential_options_for_state(state: str) -> list[dict[str, str]]:
    return [
        {"code": code, "label": CREDENTIAL_LABELS[code]}
        for code in credential_types_for_state(state)
    ]


def shift_role_credentials_for_state(shift_role: str, facility_state: str) -> tuple[str, ...]:
    role = normalize_shift_role(shift_role)
    base = ROLE_CREDENTIAL_MAP.get(role, ())
    state = normalize_state(facility_state)
    if role == "GNA":
        if state in GNA_LICENSE_STATES:
            return ("GNA", "CNA")
        return ("CNA", "NA")
    return base


def normalize_state(value: str | None, *, default: str = "MD") -> str:
    from app.services.states import normalize_state as _normalize_state

    return _normalize_state(value, default=default)


def credential_valid_in_state(credential_type: str, state: str) -> bool:
    cred = normalize_credential_type(credential_type)
    if cred == "GNA":
        return normalize_state(state) in GNA_LICENSE_STATES
    return True


def clinician_qualifies_for_shift_role(
    credential_type: str,
    shift_role: str,
    *,
    facility_state: str | None = None,
) -> bool:
    cred = normalize_credential_type(credential_type)
    role = normalize_shift_role(shift_role)
    if facility_state:
        allowed = shift_role_credentials_for_state(role, facility_state)
    else:
        allowed = ROLE_CREDENTIAL_MAP.get(role, ())
    return cred in allowed


def requires_npi(credential_type: str) -> bool:
    return normalize_credential_type(credential_type) not in NON_NPI_CREDENTIALS


def infer_credential_from_license(license_number: str) -> str | None:
    token = str(license_number or "").strip().upper()
    if token.startswith("RN-"):
        return "RN"
    if token.startswith("LPN-"):
        return "LPN"
    if token.startswith("CNA-"):
        return "CNA"
    if token.startswith("GNA-"):
        return "GNA"
    if token.startswith("NA-"):
        return "NA"
    return None


def synthetic_npi_for_caregiver(seed_text: str) -> str:
    from app.services.license_verification import is_valid_npi

    digest = abs(hash(f"offercare:{seed_text.strip().lower()}")) % 1_000_000_000
    base9 = f"{digest:09d}"
    for check in range(10):
        candidate = f"{base9}{check}"
        if is_valid_npi(candidate):
            return candidate
    return "1234567893"


def map_scraped_facility_type(raw: str) -> str:
    lowered = str(raw or "").lower()
    if "nursing home" in lowered or "skilled nursing" in lowered or "snf" in lowered:
        return "NURSING_HOME"
    if "home health" in lowered or "home care" in lowered or "hha" in lowered:
        return "HOME_HEALTH"
    if "hospital" in lowered or "acute care" in lowered:
        return "HOSPITAL"
    if "urgent" in lowered:
        return "URGENT_CARE"
    return "HEALTHCARE"


def provider_supports_facility_type(service_lines: str, facility_type: str) -> bool:
    tokens = {token.strip().upper() for token in str(service_lines or "ALL").split(",") if token.strip()}
    if "ALL" in tokens:
        return True
    return normalize_facility_type(facility_type) in tokens


PORTAL_SERVICE_LINE_OPTIONS: tuple[str, ...] = ("ALL", "HOSPITAL", "NURSING_HOME", "HOME_HEALTH")


def normalize_service_lines(value: str | list[str]) -> str:
    if isinstance(value, list):
        tokens = [str(item).strip().upper() for item in value if str(item).strip()]
    else:
        tokens = [token.strip().upper() for token in str(value or "").split(",") if token.strip()]
    if not tokens:
        raise ValueError("service_lines_required")
    if "ALL" in tokens:
        return "ALL"
    allowed = set(FACILITY_TYPES)
    invalid = [token for token in tokens if token not in allowed]
    if invalid:
        raise ValueError("invalid_service_lines")
    seen: set[str] = set()
    cleaned: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return ",".join(cleaned)


def service_line_options() -> list[dict[str, str]]:
    return [
        {"code": "ALL", "label": "All care settings"},
        *[
            {"code": code, "label": FACILITY_TYPE_LABELS[code]}
            for code in ("HOSPITAL", "NURSING_HOME", "HOME_HEALTH")
        ],
    ]


def default_service_lines_for_credential(credential_type: str) -> str:
    cred = normalize_credential_type(credential_type)
    if cred == "RN":
        return "ALL"
    if cred == "LPN":
        return "NURSING_HOME,HOME_HEALTH"
    return "NURSING_HOME,HOME_HEALTH"


def care_taxonomy_snapshot() -> dict:
    return {
        "facility_types": [
            {"code": code, "label": FACILITY_TYPE_LABELS[code]} for code in FACILITY_TYPES
        ],
        "credential_types": [
            {"code": code, "label": CREDENTIAL_LABELS[code]} for code in CREDENTIAL_TYPES
        ],
        "shift_roles": [
            {"code": code, "label": SHIFT_ROLE_LABELS[code]} for code in SHIFT_ROLES
        ],
        "shift_templates_by_facility_type": {
            facility_type: [{"shift_role": role, "hourly_pay_rate": rate} for role, rate in templates]
            for facility_type, templates in SHIFT_TEMPLATES_BY_FACILITY_TYPE.items()
        },
        "state_credential_rules": {
            "gna_license_states": sorted(GNA_LICENSE_STATES),
            "gna_shift_fills_with_cna_in": ["PA", "VA", "DE", "NJ"],
            "note": "GNA is a Maryland/DC credential; PA and other states staff GNA shifts with CNA.",
        },
    }
