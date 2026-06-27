"""Maryland LTC compliance validator — deterministic placement gate for CNA / GNA / LPN.

Core API: ``MarylandComplianceValidator.validate_for_facility(provider, facility)``.

Integrates with ``maryland_providers`` via optional DB adapters (``verify_provider_md_licensure``).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LicenseVerificationLog, MarylandProvider, MdProviderLicensure
from app.services.care_taxonomy import normalize_credential_type
from app.services.mbon_verification import MbonVerificationResult, verify_mbon_license

# ---------------------------------------------------------------------------
# Constants (shared with credentialing pipeline + API routes)
# ---------------------------------------------------------------------------

REJECTED_COMPLIANCE = "REJECTED_COMPLIANCE"
EXPIRY_BLOCK_DAYS = 30

MD_LTC_CREDENTIALS = frozenset({"LPN", "CNA", "GNA"})
MD_FACILITY_TYPES = frozenset({"SNF", "ALF", "HHA"})

LICENSE_PATTERNS: dict[str, re.Pattern[str]] = {
    "LPN": re.compile(r"^(LPN|PN)[A-Z0-9\-]{2,24}$", re.I),
    "CNA": re.compile(r"^(CNA|NA|GNA)[A-Z0-9\-]{2,24}$", re.I),
    "GNA": re.compile(r"^(GNA|CNA)[A-Z0-9\-]{2,24}$", re.I),
}


# ---------------------------------------------------------------------------
# Domain payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderCompliancePayload:
    """Normalized provider credential snapshot for validation."""

    credential_type: str
    license_number: str
    license_expires_on: datetime | None = None
    has_gna_endorsement: bool = False
    compact_multistate: bool = False
    ohcq_sanction_flag: bool = False
    mbon_status: str | None = None
    home_county: str | None = None


@dataclass(frozen=True)
class FacilityTarget:
    """Target placement facility for compliance routing."""

    facility_type: str
    county: str | None = None


@dataclass
class ComplianceValidationResult:
    compliant: bool
    compliance_status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    days_to_expiry: int | None = None


class ComplianceRejection(Exception):
    """Raised when a provider fails Maryland placement compliance for a facility type."""

    def __init__(self, code: str, message: str, *, errors: list[str] | None = None) -> None:
        self.code = code
        self.message = message
        self.errors = list(errors or [code])
        super().__init__(message)


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------


class MarylandComplianceValidator:
    """Deterministic Maryland licensure + placement compliance gate."""

    EXPIRY_BUFFER_DAYS = EXPIRY_BLOCK_DAYS
    MD_LTC_CREDENTIALS = MD_LTC_CREDENTIALS
    MD_FACILITY_TYPES = MD_FACILITY_TYPES

    def validate_for_facility(
        self,
        provider: ProviderCompliancePayload,
        facility: FacilityTarget,
        *,
        raise_on_reject: bool = False,
    ) -> ComplianceValidationResult:
        """Validate provider credentials against a targeted Maryland facility type."""
        errors: list[str] = []
        warnings: list[str] = []

        cred = normalize_credential_type(provider.credential_type)
        facility_type = str(facility.facility_type or "").strip().upper()

        if cred not in self.MD_LTC_CREDENTIALS:
            errors.append("unsupported_credential_type")
        if facility_type and facility_type not in self.MD_FACILITY_TYPES:
            errors.append("unsupported_facility_type")

        if is_malformed_license_number(cred, provider.license_number):
            errors.append("malformed_license_number")

        expiry_error, days_left = self._check_expiry_buffer(provider.license_expires_on)
        if expiry_error:
            errors.append(expiry_error)

        if provider.ohcq_sanction_flag:
            errors.append("ohcq_sanction_active")
        if str(provider.mbon_status or "").upper() in {"EXPIRED", "DISCIPLINE", "NOT_FOUND"}:
            errors.append(f"mbon_status_{str(provider.mbon_status).lower()}")

        if cred == "LPN":
            lpn_error = self._check_lpn_license(provider)
            if lpn_error:
                errors.append(lpn_error)
        elif cred in {"CNA", "GNA"}:
            gna_error = self._check_snf_gna_requirement(
                credential_type=cred,
                facility_type=facility_type,
                has_gna_endorsement=provider.has_gna_endorsement,
            )
            if gna_error:
                errors.append(gna_error)

        compliant = len(errors) == 0
        if compliant and days_left is not None and days_left <= self.EXPIRY_BUFFER_DAYS:
            warnings.append(f"license_expires_in_{days_left}_days")

        status = "COMPLIANT" if compliant else "NON_COMPLIANT"
        if not compliant and any(
            token in errors
            for token in (
                "license_expires_within_buffer",
                "ohcq_sanction_active",
                "missing_gna_endorsement_snf",
                "mbon_status_expired",
                "mbon_status_discipline",
                "mbon_status_not_found",
            )
        ):
            status = REJECTED_COMPLIANCE

        result = ComplianceValidationResult(
            compliant=compliant,
            compliance_status=status,
            errors=errors,
            warnings=warnings,
            days_to_expiry=days_left,
        )

        if raise_on_reject and not compliant:
            raise ComplianceRejection(
                code=status,
                message="; ".join(errors),
                errors=errors,
            )
        return result

    def _check_expiry_buffer(
        self,
        expires_on: datetime | None,
    ) -> tuple[str | None, int | None]:
        if expires_on is None:
            return None, None
        now = datetime.now(timezone.utc)
        if expires_on.tzinfo is None:
            expires_on = expires_on.replace(tzinfo=timezone.utc)
        days_left = (expires_on - now).days
        if days_left <= 0:
            return "license_expired", days_left
        if days_left <= self.EXPIRY_BUFFER_DAYS:
            return "license_expires_within_buffer", days_left
        return None, days_left

    def _check_lpn_license(self, provider: ProviderCompliancePayload) -> str | None:
        status = str(provider.mbon_status or "").upper()
        if status == "ACTIVE":
            return None
        if provider.compact_multistate:
            return None
        return "lpn_not_active_or_compact"

    def _check_snf_gna_requirement(
        self,
        *,
        credential_type: str,
        facility_type: str,
        has_gna_endorsement: bool,
    ) -> str | None:
        """Maryland law: CNAs in SNFs must hold GNA endorsement."""
        if facility_type != "SNF":
            return None
        if credential_type == "GNA":
            return None if has_gna_endorsement else "missing_gna_endorsement_snf"
        if credential_type == "CNA" and not has_gna_endorsement:
            return "missing_gna_endorsement_snf"
        return None


# ---------------------------------------------------------------------------
# Helpers + DB integration (credentialing pipeline / batch API)
# ---------------------------------------------------------------------------


def normalize_license_number(raw: str | None) -> str:
    return re.sub(r"\s+", "", str(raw or "").strip().upper())


def is_malformed_license_number(credential_type: str, license_number: str) -> bool:
    token = normalize_license_number(license_number)
    if len(token) < 4:
        return True
    cred = normalize_credential_type(credential_type)
    if cred not in MD_LTC_CREDENTIALS:
        return len(token) < 5
    pattern = LICENSE_PATTERNS.get(cred)
    if pattern is None:
        return not bool(re.match(r"^[A-Z0-9][A-Z0-9\-]{3,48}$", token))
    return pattern.match(token) is None


@dataclass(frozen=True)
class MbonLookupRequest:
    provider_id: str
    credential_type: str
    license_number: str
    cna_license_number: str | None
    full_name: str
    facility_county: str | None
    requires_gna_endorsement: bool
    compact_eligible: bool


@dataclass
class MdLicensureVerificationResult:
    ok: bool
    provider_id: str
    credential_type: str
    license_number: str
    disposition: str
    mbon_status: str | None = None
    gna_endorsement_status: bool = False
    compact_multistate: bool = False
    expires_on: datetime | None = None
    days_to_expiry: int | None = None
    ohcq_sanction_flag: bool = False
    block_dispatch: bool = False
    errors: list[str] = field(default_factory=list)
    lookup_request: dict[str, Any] | None = None


def _parse_gna_endorsement(mbon: MbonVerificationResult, credential_type: str) -> bool:
    cred = normalize_credential_type(credential_type)
    raw = mbon.raw if isinstance(mbon.raw, dict) else {}
    if "gna_endorsement" in raw:
        return bool(raw.get("gna_endorsement"))
    if cred == "GNA":
        return mbon.status == "ACTIVE"
    if cred == "CNA":
        return bool(raw.get("gna_endorsement")) or str(raw.get("endorsements") or "").upper().find("GNA") >= 0
    return False


def _parse_compact_multistate(mbon: MbonVerificationResult, credential_type: str) -> bool:
    if normalize_credential_type(credential_type) != "LPN":
        return False
    raw = mbon.raw if isinstance(mbon.raw, dict) else {}
    compact_token = str(raw.get("compact_status") or raw.get("multistate") or "").upper()
    if compact_token in {"ACTIVE", "COMPACT", "MULTISTATE", "TRUE", "YES"}:
        return True
    license_token = str(mbon.license_number or "").upper()
    return license_token.startswith("NLC") or "-COMPACT" in license_token


def build_mbon_lookup_request(
    provider: MarylandProvider,
    *,
    profile: MdProviderLicensure | None = None,
) -> MbonLookupRequest | None:
    cred = normalize_credential_type(provider.credential_type)
    license_number = normalize_license_number(provider.md_license_number)
    if is_malformed_license_number(cred, license_number):
        return None
    cna_number = None
    if cred in {"CNA", "GNA"}:
        if profile and profile.cna_license_number:
            cna_number = normalize_license_number(profile.cna_license_number)
        else:
            cna_number = license_number
    county = profile.facility_county.strip() if profile and profile.facility_county else None
    return MbonLookupRequest(
        provider_id=str(provider.provider_id),
        credential_type=cred,
        license_number=license_number,
        cna_license_number=cna_number,
        full_name=str(provider.full_name or "").strip(),
        facility_county=county,
        requires_gna_endorsement=cred in {"CNA", "GNA"},
        compact_eligible=cred == "LPN",
    )


def get_or_create_licensure_profile(db: Session, provider: MarylandProvider) -> MdProviderLicensure:
    row = (
        db.query(MdProviderLicensure)
        .filter(MdProviderLicensure.provider_id == provider.provider_id)
        .first()
    )
    if row is not None:
        return row
    cred = normalize_credential_type(provider.credential_type)
    cna_number = normalize_license_number(provider.md_license_number) if cred in {"CNA", "GNA"} else None
    row = MdProviderLicensure(
        profile_id=uuid.uuid4(),
        provider_id=provider.provider_id,
        cna_license_number=cna_number,
        gna_endorsement_status=False,
    )
    db.add(row)
    db.flush()
    return row


def apply_compliance_block(db: Session, provider: MarylandProvider, *, reason: str) -> None:
    provider.license_status = REJECTED_COMPLIANCE
    provider.dispatch_status = "SUSPENDED"
    provider.verification_notes = reason[:500]
    db.add(
        LicenseVerificationLog(
            provider_id=provider.provider_id,
            event_type="MD_LICENSURE_BLOCK",
            check_result=REJECTED_COMPLIANCE,
            notes=reason[:500],
            reviewer="md_licensure_validator",
        )
    )


def verify_provider_md_licensure(
    db: Session | None,
    provider: MarylandProvider,
    *,
    profile: MdProviderLicensure | None = None,
    facility_type: str = "SNF",
) -> MdLicensureVerificationResult:
    """Run MBON lookup + ``MarylandComplianceValidator`` for one provider."""
    cred = normalize_credential_type(provider.credential_type)
    license_number = normalize_license_number(provider.md_license_number)
    result = MdLicensureVerificationResult(
        ok=False,
        provider_id=str(provider.provider_id),
        credential_type=cred,
        license_number=license_number,
        disposition="SKIPPED_MALFORMED",
    )

    if cred not in MD_LTC_CREDENTIALS:
        result.disposition = "SKIPPED_UNSUPPORTED_CREDENTIAL"
        result.errors.append("unsupported_credential_for_md_ltc_module")
        return result

    if is_malformed_license_number(cred, license_number):
        result.errors.append("malformed_license_number")
        return result

    profile = profile or get_or_create_licensure_profile(db, provider)
    lookup = build_mbon_lookup_request(provider, profile=profile)
    if lookup is None:
        result.errors.append("lookup_request_build_failed")
        return result
    result.lookup_request = asdict(lookup)

    try:
        mbon = verify_mbon_license(provider)
    except Exception as exc:  # noqa: BLE001 — queue must not freeze
        result.disposition = "LOOKUP_ERROR"
        result.errors.append(f"mbon_lookup_error:{type(exc).__name__}")
        return result

    gna_ok = _parse_gna_endorsement(mbon, cred)
    compact_ok = _parse_compact_multistate(mbon, cred)
    validator = MarylandComplianceValidator()
    validation = validator.validate_for_facility(
        ProviderCompliancePayload(
            credential_type=cred,
            license_number=license_number,
            license_expires_on=mbon.expires_on,
            has_gna_endorsement=gna_ok,
            compact_multistate=compact_ok,
            ohcq_sanction_flag=bool(mbon.disciplinary_action),
            mbon_status=mbon.status,
            home_county=profile.facility_county,
        ),
        FacilityTarget(facility_type=facility_type, county=profile.facility_county),
    )

    result.mbon_status = mbon.status
    result.expires_on = mbon.expires_on
    result.days_to_expiry = validation.days_to_expiry
    result.ohcq_sanction_flag = bool(mbon.disciplinary_action)
    result.gna_endorsement_status = gna_ok
    result.compact_multistate = compact_ok
    result.errors.extend(validation.errors)
    result.block_dispatch = not validation.compliant

    now = datetime.now(timezone.utc)
    profile.cna_license_number = lookup.cna_license_number
    profile.gna_endorsement_status = gna_ok
    profile.mbon_status_last_checked = now
    profile.mbon_last_status = mbon.status
    profile.mbon_expires_on = mbon.expires_on
    profile.ohcq_sanction_flag = result.ohcq_sanction_flag
    profile.compact_multistate = compact_ok
    profile.verification_payload_json = json.dumps(
        {
            "lookup": result.lookup_request,
            "validation": {
                "compliant": validation.compliant,
                "status": validation.compliance_status,
                "errors": validation.errors,
            },
            "mbon": {
                "status": mbon.status,
                "expires_on": mbon.expires_on.isoformat() if mbon.expires_on else None,
                "disciplinary_action": mbon.disciplinary_action,
            },
        }
    )
    profile.updated_at = now

    if result.block_dispatch:
        apply_compliance_block(db, provider, reason="; ".join(result.errors))
        result.disposition = REJECTED_COMPLIANCE
    else:
        if str(provider.license_status or "").upper() not in {REJECTED_COMPLIANCE, "REJECTED"}:
            provider.license_status = "VERIFIED"
            provider.dispatch_status = "ACTIVE"
            provider.last_verified_timestamp = now
        result.disposition = "VERIFIED"
        result.ok = True

    db.commit()
    db.refresh(provider)
    return result


def run_md_licensure_batch(
    db: Session,
    *,
    credential_types: tuple[str, ...] = ("LPN", "CNA", "GNA"),
    limit: int = 100,
) -> dict[str, Any]:
    cred_set = {normalize_credential_type(token) for token in credential_types}
    providers = (
        db.query(MarylandProvider)
        .filter(
            MarylandProvider.state == "MD",
            MarylandProvider.credential_type.in_(sorted(cred_set)),
        )
        .order_by(MarylandProvider.applied_at.asc())
        .limit(limit)
        .all()
    )
    summary = {"verified": 0, "rejected": 0, "skipped_malformed": 0, "lookup_errors": 0, "results": []}
    for provider in providers:
        outcome = verify_provider_md_licensure(db, provider)
        row = {
            "provider_id": outcome.provider_id,
            "credential_type": outcome.credential_type,
            "disposition": outcome.disposition,
            "errors": outcome.errors,
        }
        summary["results"].append(row)
        if outcome.disposition == "VERIFIED":
            summary["verified"] += 1
        elif outcome.disposition == REJECTED_COMPLIANCE:
            summary["rejected"] += 1
        elif outcome.disposition == "LOOKUP_ERROR":
            summary["lookup_errors"] += 1
        else:
            summary["skipped_malformed"] += 1
    return summary


# ---------------------------------------------------------------------------
# Local terminal self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    validator = MarylandComplianceValidator()
    future = datetime.now(timezone.utc) + timedelta(days=90)

    # 1) Compliant GNA at SNF
    ok = validator.validate_for_facility(
        ProviderCompliancePayload(
            credential_type="GNA",
            license_number="GNA-MD-10001",
            license_expires_on=future,
            has_gna_endorsement=True,
            mbon_status="ACTIVE",
        ),
        FacilityTarget(facility_type="SNF", county="Baltimore"),
    )
    assert ok.compliant is True, ok.errors

    # 2) CNA at SNF without GNA endorsement → rejection
    rejected = False
    try:
        validator.validate_for_facility(
            ProviderCompliancePayload(
                credential_type="CNA",
                license_number="CNA-MD-20002",
                license_expires_on=future,
                has_gna_endorsement=False,
                mbon_status="ACTIVE",
            ),
            FacilityTarget(facility_type="SNF", county="Montgomery"),
            raise_on_reject=True,
        )
    except ComplianceRejection as exc:
        rejected = True
        assert "missing_gna_endorsement_snf" in exc.errors
    assert rejected is True

    # 3) CNA at ALF — GNA not required
    alf_ok = validator.validate_for_facility(
        ProviderCompliancePayload(
            credential_type="CNA",
            license_number="CNA-MD-30003",
            license_expires_on=future,
            has_gna_endorsement=False,
            mbon_status="ACTIVE",
        ),
        FacilityTarget(facility_type="ALF", county="Howard"),
    )
    assert alf_ok.compliant is True, alf_ok.errors

    # 4) License expiring within 30-day buffer
    soon = datetime.now(timezone.utc) + timedelta(days=14)
    expiring = validator.validate_for_facility(
        ProviderCompliancePayload(
            credential_type="LPN",
            license_number="LPN-MD-40004",
            license_expires_on=soon,
            compact_multistate=True,
            mbon_status="ACTIVE",
        ),
        FacilityTarget(facility_type="HHA", county="Anne Arundel"),
    )
    assert expiring.compliant is False
    assert "license_expires_within_buffer" in expiring.errors

    # 5) Malformed license exits cleanly
    bad = validator.validate_for_facility(
        ProviderCompliancePayload(credential_type="CNA", license_number="XX"),
        FacilityTarget(facility_type="SNF"),
    )
    assert bad.compliant is False
    assert "malformed_license_number" in bad.errors

    print("MarylandComplianceValidator: all local assertions passed.")
