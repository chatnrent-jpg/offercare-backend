"""Semantic dispatch extractor — speech/SMS text to structured shift records (lookahead-safe)."""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_UNREGISTERED_FACILITY_TOKEN = "UNREGISTERED_INBOUND_COMM_POOL"
_PERIMETER_MILES = 150.0
_VALIDATOR_RADIUS_CAP = 100.0
_DEFAULT_ROLE = "CNA"
_NIGHT_SHIFT_TAG = "NIGHT_SHIFT"
_DAY_SHIFT_TAG = "DAY_SHIFT"

_ROLE_KEYWORDS: tuple[tuple[str, ...], str] = (
    (("cna", "nurse assistant", "certified nursing assistant", "certified"), _DEFAULT_ROLE),
)
_NIGHT_KEYWORDS = ("night", "overnight", "11pm", "11 pm", "graveyard", "third shift", "3rd shift")
_CARE_TAG_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("dementia", "dementia"),
    ("memory care", "memory_care"),
    ("compliance", "compliance"),
)
_MONTH_LOOKUP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class SemanticDispatchHardStop(RuntimeError):
    """Hive halt — semantic dispatch extractor compile or dependency failure."""


@dataclass(frozen=True, slots=True)
class FacilityResolution:
    facility_token: str
    facility_id: str | None
    facility_name: str | None
    latitude: float | None
    longitude: float | None
    phone_match: bool


@dataclass(frozen=True, slots=True)
class ShiftParameterExtraction:
    role_type: str
    shift_tag: str | None
    specialized_care_tags: tuple[str, ...]
    shift_date: date
    shift_date_iso: str
    raw_payload_text: str
    sentinel_geo_ok: bool
    sentinel_geo_detail: dict[str, Any] = field(default_factory=dict)


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _normalize_phone_digits(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def _lazy_session_local():
    try:
        from app.database import SessionLocal
    except Exception as exc:  # noqa: BLE001
        raise SemanticDispatchHardStop("database_session_import_failed") from exc
    return SessionLocal


def _lazy_maryland_facility_model():
    try:
        from app.models import MarylandFacility
    except Exception as exc:  # noqa: BLE001
        raise SemanticDispatchHardStop("maryland_facility_import_failed") from exc
    return MarylandFacility


def _import_sentinel_validation() -> tuple[Any, Any]:
    try:
        from app.schemas.sentinel_validation import (  # type: ignore[import-not-found]
            FacilityGeoInputValidator,
            SentinelValidationSuite,
            format_sentinel_validation_error,
        )

        return SentinelValidationSuite, format_sentinel_validation_error
    except ImportError:
        module_path = _REPO_ROOT / "app" / "schemas" / "sentinel_validation.py"
        spec = importlib.util.spec_from_file_location("sentinel_validation", module_path)
        if spec is None or spec.loader is None:
            raise SemanticDispatchHardStop("sentinel_validation_import_failed") from None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.SentinelValidationSuite, module.format_sentinel_validation_error


def _facility_resolution_from_row(row: Any) -> FacilityResolution:
    facility_id = str(getattr(row, "facility_id", "") or "") or None
    latitude = getattr(row, "latitude", None)
    longitude = getattr(row, "longitude", None)
    return FacilityResolution(
        facility_token=facility_id or _UNREGISTERED_FACILITY_TOKEN,
        facility_id=facility_id,
        facility_name=str(getattr(row, "name", "") or "") or None,
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        phone_match=True,
    )


def _unregistered_facility_resolution() -> FacilityResolution:
    return FacilityResolution(
        facility_token=_UNREGISTERED_FACILITY_TOKEN,
        facility_id=None,
        facility_name=None,
        latitude=None,
        longitude=None,
        phone_match=False,
    )


class SemanticDispatchExtractor:
    """Parse inbound voice/SMS payloads into lookahead-safe structured shift records."""

    def __init__(self, db: Any | None = None) -> None:
        self._db = db
        self._owned_session: Any | None = None

    def _session(self) -> Any:
        if self._db is not None:
            return self._db
        if self._owned_session is None:
            session_factory = _lazy_session_local()
            self._owned_session = session_factory()
        return self._owned_session

    def close(self) -> None:
        if self._owned_session is not None:
            self._owned_session.close()
            self._owned_session = None

    def resolve_incoming_facility(self, from_phone: str) -> FacilityResolution:
        """Match inbound caller phone to an active maryland_facilities record."""
        target_digits = _normalize_phone_digits(from_phone)
        if not target_digits:
            return _unregistered_facility_resolution()

        try:
            db = self._session()
            MarylandFacility = _lazy_maryland_facility_model()
            rows = (
                db.query(MarylandFacility)
                .filter(MarylandFacility.phone.isnot(None))
                .all()
            )
            for row in rows:
                stored_digits = _normalize_phone_digits(str(getattr(row, "phone", "") or ""))
                if stored_digits and stored_digits == target_digits:
                    return _facility_resolution_from_row(row)
        except SemanticDispatchHardStop:
            raise
        except Exception:
            logger.exception("facility phone lookup failed from_phone_tail=%s", target_digits[-4:])
            return _unregistered_facility_resolution()

        return _unregistered_facility_resolution()

    def _detect_role_type(self, normalized_text: str) -> str:
        for keywords, role in _ROLE_KEYWORDS:
            for keyword in keywords:
                if keyword in normalized_text:
                    return role
        return _DEFAULT_ROLE

    def _detect_shift_tag(self, normalized_text: str) -> str | None:
        for keyword in _NIGHT_KEYWORDS:
            if keyword in normalized_text:
                return _NIGHT_SHIFT_TAG
        if any(token in normalized_text for token in ("day shift", "dayshift", "morning shift")):
            return _DAY_SHIFT_TAG
        return None

    def _detect_care_tags(self, normalized_text: str) -> tuple[str, ...]:
        tags: list[str] = []
        for needle, tag in _CARE_TAG_KEYWORDS:
            if needle in normalized_text:
                tags.append(tag)
        return tuple(tags)

    def _resolve_shift_date(self, raw_text: str, execution_boundary: date) -> date:
        lowered = str(raw_text or "").lower()

        if re.search(r"\btomorrow\b", lowered):
            return execution_boundary + timedelta(days=1)
        if re.search(r"\btoday\b", lowered):
            return execution_boundary

        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
            r"\s+(\d{1,2})(?:,?\s+(\d{4}))?\b",
            lowered,
        )
        if month_match:
            month_name, day_token, year_token = month_match.groups()
            month = _MONTH_LOOKUP[month_name.lower()]
            day = int(day_token)
            year = int(year_token) if year_token else execution_boundary.year
            return date(year, month, day)

        mdy_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", lowered)
        if mdy_match:
            month_token, day_token, year_token = mdy_match.groups()
            month = int(month_token)
            day = int(day_token)
            if year_token:
                year = int(year_token)
                if year < 100:
                    year += 2000
            else:
                year = execution_boundary.year
            return date(year, month, day)

        return execution_boundary

    def _sentinel_intercept_facility_geo(self, facility: FacilityResolution | None) -> dict[str, Any]:
        """Pass facility geographic center through FacilityGeoInputValidator (150-mile guard)."""
        if facility is None or facility.latitude is None or facility.longitude is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "facility_geo_unavailable",
            }

        perimeter_radius = min(_PERIMETER_MILES, _VALIDATOR_RADIUS_CAP)
        geo_payload = {
            "latitude": float(facility.latitude),
            "longitude": float(facility.longitude),
            "search_radius_miles": float(perimeter_radius),
        }

        try:
            suite_cls, _format_error = _import_sentinel_validation()
            validated = suite_cls.validate_facility_geo_input(geo_payload)
            return {
                "ok": True,
                "skipped": False,
                "perimeter_miles": _PERIMETER_MILES,
                "validated": validated.model_dump(),
            }
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
            try:
                from pydantic import ValidationError

                if isinstance(exc, ValidationError):
                    _, format_error = _import_sentinel_validation()
                    detail = json.dumps(format_error(exc))
            except Exception:  # noqa: BLE001
                pass
            logger.warning("HIVE_COMM_ALERT sentinel geo intercept blocked: %s", detail)
            return {
                "ok": False,
                "skipped": False,
                "perimeter_miles": _PERIMETER_MILES,
                "error": detail,
            }

    def extract_shift_parameters(
        self,
        raw_payload_text: str,
        *,
        facility: FacilityResolution | None = None,
        execution_boundary: date | None = None,
    ) -> ShiftParameterExtraction:
        """Tokenize inbound text into role, shift tag, care tags, and lookahead-safe shift date."""
        boundary = execution_boundary or _utc_today()
        normalized_text = re.sub(r"\s+", " ", str(raw_payload_text or "").strip().lower())

        role_type = self._detect_role_type(normalized_text)
        shift_tag = self._detect_shift_tag(normalized_text)
        care_tags = self._detect_care_tags(normalized_text)
        shift_date = self._resolve_shift_date(raw_payload_text, boundary)
        sentinel_geo = self._sentinel_intercept_facility_geo(facility)

        if not sentinel_geo.get("ok", False):
            raise ValueError(f"SENTINEL_BLOCK:{json.dumps(sentinel_geo)}")

        return ShiftParameterExtraction(
            role_type=role_type,
            shift_tag=shift_tag,
            specialized_care_tags=care_tags,
            shift_date=shift_date,
            shift_date_iso=shift_date.isoformat(),
            raw_payload_text=str(raw_payload_text or ""),
            sentinel_geo_ok=True,
            sentinel_geo_detail=sentinel_geo,
        )


if __name__ == "__main__":
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

    extractor = SemanticDispatchExtractor(db=None)

    boundary = date(2026, 6, 28)
    sample_text = (
        "Need a CNA for tomorrow night shift — dementia memory care unit, compliance review ready."
    )
    extraction = extractor.extract_shift_parameters(
        sample_text,
        facility=_unregistered_facility_resolution(),
        execution_boundary=boundary,
    )

    assert extraction.role_type == _DEFAULT_ROLE
    assert extraction.shift_tag == _NIGHT_SHIFT_TAG
    assert extraction.shift_date == date(2026, 6, 29)
    assert "dementia" in extraction.specialized_care_tags
    assert "memory_care" in extraction.specialized_care_tags
    assert "compliance" in extraction.specialized_care_tags
    assert extraction.sentinel_geo_ok is True

    unregistered = extractor.resolve_incoming_facility("")
    assert unregistered.facility_token == _UNREGISTERED_FACILITY_TOKEN

    print("COMPILE_OK semantic_dispatch_extractor")
    print(f"  shift_date={extraction.shift_date_iso}")
    print(f"  shift_tag={extraction.shift_tag}")
    print(f"  care_tags={list(extraction.specialized_care_tags)}")
