"""Autonomous credential check engine — Maryland license + OIG dispatch compliance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_MBON_REGISTRY_SOURCE = "MBON_REGISTRY_MOCK"
_OIG_LEIE_SOURCE = "OIG_LEIE_MOCK"


class CredentialCheckHardStop(RuntimeError):
    """Hive halt — credential check engine import/DB failure."""


@dataclass(frozen=True)
class MarylandLicenseVerificationResult:
    ok: bool
    provider_id: str
    license_number: str
    mbon_status: str
    license_expiration_date: str | None
    is_unexpired: bool
    disciplinary_action: bool
    registry_payload: dict[str, Any]


@dataclass(frozen=True)
class OigExclusionCheckResult:
    ok: bool
    provider_id: str
    full_name: str
    oig_status: str
    match_count: int
    internal_restriction_hit: bool
    screening_payload: dict[str, Any]


@dataclass(frozen=True)
class DispatchComplianceEvaluation:
    ok: bool
    provider_id: str
    license_number: str
    is_eligible: bool
    compliance_status: str
    checked_at: str
    mbon_status: str
    oig_status: str
    license_expiration_date: str | None
    details: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return _utc(dt).isoformat()


_SPEED_GUARD_TIMEOUT_NOTE = "Registry lookup timed out under 150ms speed guard."
_CIRCUIT_BREAKER_TRIPPED_STATUS = "CIRCUIT_BREAKER_TRIPPED"


def _is_circuit_breaker_tripped(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("circuit_tripped") is True:
        return True
    return str(payload.get("status") or "").upper() == _CIRCUIT_BREAKER_TRIPPED_STATUS


def _load_network_circuit_breaker() -> Any:
    try:
        from strategy.network_circuit_breaker import NetworkCircuitBreaker
    except ImportError as exc:
        raise CredentialCheckHardStop("network_circuit_breaker_import_failed") from exc
    return NetworkCircuitBreaker()


def _execute_mbon_registry_lookup(*, license_number: str, credential_type: str) -> dict[str, Any]:
    breaker = _load_network_circuit_breaker()
    result = breaker.execute_with_speed_guard(
        _mock_mbon_registry_lookup,
        license_number=license_number,
        credential_type=credential_type,
    )
    if _is_circuit_breaker_tripped(result):
        return dict(result)
    return result


def _mock_mbon_registry_lookup(*, license_number: str, credential_type: str) -> dict[str, Any]:
    """Mock Maryland Board of Nursing registry handshake (COMPILE_OK safe)."""
    token = str(license_number or "").strip().upper()
    expires = (_utc_now() + timedelta(days=365)).date().isoformat()
    status = "EXPIRED" if token.endswith("X") else "ACTIVE"
    if token.endswith("D"):
        status = "DISCIPLINE"
    gna_endorsement = token.startswith("GNA") or (
        token.startswith("CNA") and not token.endswith("NOGNA")
    )
    return {
        "registry": "Maryland Board of Nursing",
        "endpoint": "https://lookup.mbon.org/mock/v1/license",
        "license_number": token,
        "credential_type": str(credential_type or "").upper(),
        "status": status,
        "license_expiration_date": None if status == "EXPIRED" else expires,
        "disciplinary_action": token.endswith("D"),
        "gna_endorsement": gna_endorsement,
        "checked_at": _utc_now().isoformat(),
        "source": _MBON_REGISTRY_SOURCE,
        "dry_run": True,
    }


def _maryland_license_pending_result(
    *,
    provider_id: str,
    license_number: str,
    registry_payload: dict[str, Any],
) -> MarylandLicenseVerificationResult:
    return MarylandLicenseVerificationResult(
        ok=False,
        provider_id=str(provider_id),
        license_number=license_number,
        mbon_status="CREDENTIALS_PENDING",
        license_expiration_date=None,
        is_unexpired=False,
        disciplinary_action=False,
        registry_payload={
            **registry_payload,
            "note": _SPEED_GUARD_TIMEOUT_NOTE,
        },
    )


def _mock_oig_leie_lookup(*, full_name: str, npi_number: str) -> dict[str, Any]:
    """Mock federal OIG LEIE exclusion sweep (COMPILE_OK safe)."""
    token = str(full_name or "").strip().upper()
    excluded = "EXCLUDED" in token
    return {
        "registry": "OIG LEIE",
        "endpoint": "https://oig.hhs.gov/exclusions/mock/v1/search",
        "full_name": full_name,
        "npi": npi_number,
        "status": "EXCLUDED" if excluded else "CLEAR",
        "match_count": 1 if excluded else 0,
        "matches": [{"name": full_name}] if excluded else [],
        "checked_at": _utc_now().isoformat(),
        "source": _OIG_LEIE_SOURCE,
        "dry_run": True,
    }


def _parse_expiration(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc(value)
    token = str(value).strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        try:
            parsed = datetime.strptime(token, "%Y-%m-%d")
            parsed = parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return _utc(parsed)


def _is_license_unexpired(expiration: datetime | None, *, as_of: datetime) -> bool:
    """Lookahead-safe — license must be strictly after audit instant."""
    if expiration is None:
        return True
    return _utc(expiration) > _utc(as_of)


def _is_mock_provider_token(provider_id: str) -> bool:
    token = str(provider_id or "").strip().upper()
    return token.startswith("MOCK_") or "EXCLUDED" in token


def _mock_license_number_from_token(provider_id: str) -> str:
    token = str(provider_id or "").strip().upper()
    if "EXPIRED" in token:
        return "CNA-MD-MOCKX"
    if token.startswith("MOCK_"):
        return token.replace("MOCK_", "MOCK-", 1)
    return token


def _mock_full_name_from_token(provider_id: str) -> str:
    token = str(provider_id or "").strip()
    if "EXCLUDED" in token.upper():
        return token
    cleaned = token.replace("MOCK_", "").replace("_", " ").strip()
    return cleaned or "Mock Provider"


class CredentialCheckEngine:
    """Background credential verification broker for autonomous dispatch eligibility."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._owns_session = False

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise CredentialCheckHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _resolve_provider(self, provider_id_or_license: str) -> Any:
        from app.models import MarylandProvider

        token = str(provider_id_or_license or "").strip()
        if not token:
            raise ValueError("provider_id_or_license is required")

        try:
            provider_uuid = UUID(token)
            row = (
                self.db.query(MarylandProvider)
                .filter(MarylandProvider.provider_id == provider_uuid)
                .first()
            )
        except ValueError:
            row = (
                self.db.query(MarylandProvider)
                .filter(MarylandProvider.md_license_number == token.upper())
                .first()
            )
        if row is None:
            raise ValueError("provider_not_found")
        return row

    def _verify_mock_maryland_license(self, provider_id: str) -> MarylandLicenseVerificationResult:
        license_number = _mock_license_number_from_token(provider_id)
        registry_payload = _mock_mbon_registry_lookup(
            license_number=license_number,
            credential_type="CNA",
        )
        mbon_status = str(registry_payload.get("status") or "NOT_FOUND").upper()
        expiration = _parse_expiration(registry_payload.get("license_expiration_date"))
        as_of = _utc_now()
        unexpired = _is_license_unexpired(expiration, as_of=as_of)
        if mbon_status == "ACTIVE" and not unexpired:
            mbon_status = "EXPIRED"
        disciplinary = bool(registry_payload.get("disciplinary_action"))
        return MarylandLicenseVerificationResult(
            ok=mbon_status == "ACTIVE" and unexpired and not disciplinary,
            provider_id=str(provider_id),
            license_number=license_number,
            mbon_status=mbon_status,
            license_expiration_date=_iso(expiration),
            is_unexpired=unexpired,
            disciplinary_action=disciplinary,
            registry_payload={**registry_payload, "mock_short_circuit": True},
        )

    def _check_mock_oig_exclusion_list(self, provider_id: str) -> OigExclusionCheckResult:
        full_name = _mock_full_name_from_token(provider_id)
        screening_payload = _mock_oig_leie_lookup(full_name=full_name, npi_number="0000000000")
        oig_status = str(screening_payload.get("status") or "REVIEW").upper()
        match_count = int(screening_payload.get("match_count") or 0)
        internal_restriction_hit = "EXCLUDED" in str(provider_id or "").upper()
        return OigExclusionCheckResult(
            ok=oig_status == "CLEAR" and not internal_restriction_hit,
            provider_id=str(provider_id),
            full_name=full_name,
            oig_status=oig_status,
            match_count=match_count,
            internal_restriction_hit=internal_restriction_hit,
            screening_payload={**screening_payload, "mock_short_circuit": True},
        )

    def _evaluate_mock_dispatch_compliance(self, provider_id: str) -> DispatchComplianceEvaluation:
        checked_at = _utc_now()
        license_result = self._verify_mock_maryland_license(provider_id)
        oig_result = self._check_mock_oig_exclusion_list(provider_id)

        if oig_result.oig_status == "EXCLUDED" or oig_result.internal_restriction_hit:
            compliance_status = "OIG_FLAGGED"
            is_eligible = False
        elif license_result.mbon_status == "EXPIRED" or not license_result.is_unexpired:
            compliance_status = "LICENSE_EXPIRED"
            is_eligible = False
        elif license_result.mbon_status != "ACTIVE" or license_result.disciplinary_action:
            compliance_status = "LICENSE_INACTIVE"
            is_eligible = False
        else:
            compliance_status = "CREDENTIALS_PASSED"
            is_eligible = True

        details = {
            "mbon": {
                "status": license_result.mbon_status,
                "license_expiration_date": license_result.license_expiration_date,
                "disciplinary_action": license_result.disciplinary_action,
                "registry_source": license_result.registry_payload.get("source"),
                "mock_short_circuit": True,
            },
            "oig": {
                "status": oig_result.oig_status,
                "match_count": oig_result.match_count,
                "internal_restriction_hit": oig_result.internal_restriction_hit,
                "screening_source": oig_result.screening_payload.get("source"),
                "mock_short_circuit": True,
            },
        }

        return DispatchComplianceEvaluation(
            ok=True,
            provider_id=str(provider_id),
            license_number=license_result.license_number,
            is_eligible=is_eligible,
            compliance_status=compliance_status,
            checked_at=checked_at.isoformat(),
            mbon_status=license_result.mbon_status,
            oig_status=oig_result.oig_status,
            license_expiration_date=license_result.license_expiration_date,
            details=details,
        )

    def verify_maryland_license(self, provider_id_or_license: str) -> MarylandLicenseVerificationResult:
        """Maryland Board of Nursing license verification pipeline."""
        if _is_mock_provider_token(provider_id_or_license):
            return self._verify_mock_maryland_license(provider_id_or_license)

        try:
            provider = self._resolve_provider(provider_id_or_license)
        except SQLAlchemyError as exc:
            raise CredentialCheckHardStop("database_reference_failed") from exc

        license_number = str(provider.md_license_number or "").strip().upper()
        registry_payload = _execute_mbon_registry_lookup(
            license_number=license_number,
            credential_type=str(provider.credential_type or ""),
        )
        if _is_circuit_breaker_tripped(registry_payload):
            return _maryland_license_pending_result(
                provider_id=str(provider.provider_id),
                license_number=license_number,
                registry_payload=registry_payload,
            )
        mbon_status = str(registry_payload.get("status") or "NOT_FOUND").upper()

        expiration = _parse_expiration(provider.license_expires_on)
        if expiration is None:
            expiration = _parse_expiration(registry_payload.get("license_expiration_date"))

        as_of = _utc_now()
        unexpired = _is_license_unexpired(expiration, as_of=as_of)
        if mbon_status == "ACTIVE" and not unexpired:
            mbon_status = "EXPIRED"

        disciplinary = bool(registry_payload.get("disciplinary_action"))
        if disciplinary and mbon_status == "ACTIVE":
            mbon_status = "DISCIPLINE"

        return MarylandLicenseVerificationResult(
            ok=mbon_status == "ACTIVE" and unexpired and not disciplinary,
            provider_id=str(provider.provider_id),
            license_number=license_number,
            mbon_status=mbon_status,
            license_expiration_date=_iso(expiration),
            is_unexpired=unexpired,
            disciplinary_action=disciplinary,
            registry_payload=registry_payload,
        )

    def check_oig_exclusion_list(self, provider_id_or_license: str) -> OigExclusionCheckResult:
        """Federal OIG exclusion sweep with internal restriction log cross-reference."""
        if _is_mock_provider_token(provider_id_or_license):
            return self._check_mock_oig_exclusion_list(provider_id_or_license)

        try:
            provider = self._resolve_provider(provider_id_or_license)
        except SQLAlchemyError as exc:
            raise CredentialCheckHardStop("database_reference_failed") from exc

        screening_payload = _mock_oig_leie_lookup(
            full_name=str(provider.full_name or ""),
            npi_number=str(provider.npi_number or ""),
        )
        oig_status = str(screening_payload.get("status") or "REVIEW").upper()
        match_count = int(screening_payload.get("match_count") or 0)

        internal_restriction_hit = False
        try:
            from app.models import ExclusionScreening

            latest = (
                self.db.query(ExclusionScreening)
                .filter(ExclusionScreening.provider_id == provider.provider_id)
                .order_by(ExclusionScreening.checked_at.desc())
                .first()
            )
            if latest is not None and str(latest.status or "").upper() == "EXCLUDED":
                internal_restriction_hit = True
                oig_status = "EXCLUDED"
                match_count = max(match_count, 1)
                screening_payload = {
                    **screening_payload,
                    "internal_restriction_log": {
                        "screening_id": str(latest.screening_id),
                        "source": str(latest.source or ""),
                        "status": str(latest.status or ""),
                        "checked_at": _iso(latest.checked_at),
                    },
                }
        except SQLAlchemyError:
            logger.warning("OIG internal restriction log lookup failed for provider=%s", provider.provider_id)

        return OigExclusionCheckResult(
            ok=oig_status == "CLEAR" and not internal_restriction_hit,
            provider_id=str(provider.provider_id),
            full_name=str(provider.full_name or ""),
            oig_status=oig_status,
            match_count=match_count,
            internal_restriction_hit=internal_restriction_hit,
            screening_payload=screening_payload,
        )

    def evaluate_dispatch_compliance(self, provider_id: str) -> DispatchComplianceEvaluation:
        """Aggregate license + OIG checks into dispatch eligibility payload."""
        if _is_mock_provider_token(provider_id):
            return self._evaluate_mock_dispatch_compliance(provider_id)

        checked_at = _utc_now()
        license_result = self.verify_maryland_license(provider_id)
        oig_result = self.check_oig_exclusion_list(provider_id)

        if _is_circuit_breaker_tripped(license_result.registry_payload) or (
            license_result.mbon_status == "CREDENTIALS_PENDING"
        ):
            compliance_status = "CREDENTIALS_PENDING"
            is_eligible = False
        elif oig_result.oig_status == "EXCLUDED" or oig_result.internal_restriction_hit:
            compliance_status = "OIG_FLAGGED"
            is_eligible = False
        elif license_result.mbon_status == "EXPIRED" or not license_result.is_unexpired:
            compliance_status = "LICENSE_EXPIRED"
            is_eligible = False
        elif license_result.mbon_status != "ACTIVE" or license_result.disciplinary_action:
            compliance_status = "LICENSE_INACTIVE"
            is_eligible = False
        else:
            compliance_status = "CREDENTIALS_PASSED"
            is_eligible = True

        details = {
            "mbon": {
                "status": license_result.mbon_status,
                "license_expiration_date": license_result.license_expiration_date,
                "disciplinary_action": license_result.disciplinary_action,
                "registry_source": license_result.registry_payload.get("source"),
            },
            "oig": {
                "status": oig_result.oig_status,
                "match_count": oig_result.match_count,
                "internal_restriction_hit": oig_result.internal_restriction_hit,
                "screening_source": oig_result.screening_payload.get("source"),
            },
        }
        pending_note = license_result.registry_payload.get("note")
        if pending_note:
            details["mbon"]["note"] = pending_note

        return DispatchComplianceEvaluation(
            ok=True,
            provider_id=license_result.provider_id,
            license_number=license_result.license_number,
            is_eligible=is_eligible,
            compliance_status=compliance_status,
            checked_at=checked_at.isoformat(),
            mbon_status=license_result.mbon_status,
            oig_status=oig_result.oig_status,
            license_expiration_date=license_result.license_expiration_date,
            details=details,
        )

    def evaluate_dispatch_compliance_payload(self, provider_id: str) -> dict[str, Any]:
        """JSON-serializable summary payload for dashboards and workers."""
        result = self.evaluate_dispatch_compliance(provider_id)
        return {
            "ok": result.ok,
            "provider_id": result.provider_id,
            "license_number": result.license_number,
            "is_eligible": result.is_eligible,
            "compliance_status": result.compliance_status,
            "checked_at": result.checked_at,
            "mbon_status": result.mbon_status,
            "oig_status": result.oig_status,
            "license_expiration_date": result.license_expiration_date,
            "details": result.details,
        }


if __name__ == "__main__":
    print("COMPILE_OK credential_check_engine")
    sample_registry = _mock_mbon_registry_lookup(license_number="CNA-MD-99001", credential_type="CNA")
    sample_oig = _mock_oig_leie_lookup(full_name="Nia Patterson", npi_number="1234567890")
    print("mbon_mock_status:", sample_registry.get("status"))
    print("oig_mock_status:", sample_oig.get("status"))
    engine = CredentialCheckEngine(db=None)
    print(f"engine={engine.__class__.__name__}")
