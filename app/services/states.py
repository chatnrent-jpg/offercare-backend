"""US state helpers for multi-state grid expansion."""

from __future__ import annotations

from app.config import settings

_STATE_ALIASES = {
    "MARYLAND": "MD",
    "MD": "MD",
    "VIRGINIA": "VA",
    "VA": "VA",
    "DISTRICT OF COLUMBIA": "DC",
    "WASHINGTON DC": "DC",
    "WASHINGTON, DC": "DC",
    "DC": "DC",
    "PENNSYLVANIA": "PA",
    "PA": "PA",
    "DELAWARE": "DE",
    "DE": "DE",
    "NEW JERSEY": "NJ",
    "NJ": "NJ",
}


def supported_states() -> list[str]:
    raw = str(settings.SUPPORTED_STATES or "MD,VA,DC")
    states = []
    for token in raw.split(","):
        normalized = normalize_state(token)
        if normalized and normalized not in states:
            states.append(normalized)
    return states or ["MD"]


def normalize_state(value: str | None, *, default: str = "MD") -> str:
    token = str(value or "").strip().upper()
    if not token:
        return default
    if token in _STATE_ALIASES:
        return _STATE_ALIASES[token]
    if len(token) == 2 and token.isalpha():
        return token
    return _STATE_ALIASES.get(token, default)


def is_supported_state(value: str | None) -> bool:
    return normalize_state(value) in supported_states()


def grid_region_label() -> str:
    states = supported_states()
    if states == ["MD"]:
        return "Maryland State Wide Grid"
    return f"Mid-Atlantic Grid ({', '.join(states)})"
