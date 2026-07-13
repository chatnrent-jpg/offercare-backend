"""
Pydantic v2 Validation Schemas — Elite Security Architecture

Hyper-strict data verification for caregiver onboarding and authentication.
Zero placeholders. Production-ready. Type-safe.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ============================================================================
# ENUMS — Strict Normalized Values
# ============================================================================

class CredentialType(str, Enum):
    """
    Normalized clinical credential types.
    
    ALL inputs are normalized to these exact uppercase values.
    Variations (cna, Cna, C.N.A., etc.) automatically mapped.
    """
    RN = "RN"  # Registered Nurse
    LPN = "LPN"  # Licensed Practical Nurse
    GNA = "GNA"  # Geriatric Nursing Assistant
    CNA = "CNA"  # Certified Nursing Assistant
    NA = "NA"  # Nursing Assistant (unlicensed)


class ServiceLine(str, Enum):
    """Facility service line specializations."""
    ALL = "ALL"
    HOSPITAL = "HOSPITAL"
    URGENT_CARE = "URGENT_CARE"
    SKILLED_NURSING = "SKILLED_NURSING"
    ASSISTED_LIVING = "ASSISTED_LIVING"
    HOME_HEALTH = "HOME_HEALTH"


class USState(str, Enum):
    """Supported US states for licensure."""
    MD = "MD"
    VA = "VA"
    DC = "DC"
    PA = "PA"
    DE = "DE"
    NJ = "NJ"


# ============================================================================
# VALIDATORS — String Normalization
# ============================================================================

def normalize_credential_type(value: str) -> CredentialType:
    """
    Normalize credential type input to exact enum value.
    
    Handles variations:
    - cna, Cna, CNA → CNA
    - c.n.a., C.N.A. → CNA
    - lpn, Lpn, LPN → LPN
    - rn, Rn, RN → RN
    - gna, Gna, GNA → GNA
    
    Args:
        value: Raw input string
    
    Returns:
        Normalized CredentialType enum
    
    Raises:
        ValueError: Invalid credential type
    """
    # Remove dots, spaces, hyphens
    normalized = re.sub(r'[.\s\-_]', '', str(value)).upper()
    
    # Map variations
    credential_map = {
        "RN": CredentialType.RN,
        "LPN": CredentialType.LPN,
        "GNA": CredentialType.GNA,
        "CNA": CredentialType.CNA,
        "NA": CredentialType.NA,
        # Additional variations
        "REGISTREDNURSE": CredentialType.RN,
        "LICENSEDPRACTICALNURSE": CredentialType.LPN,
        "GERIATRICNURSINGASSISTANT": CredentialType.GNA,
        "CERTIFIEDNURSINGASSISTANT": CredentialType.CNA,
        "NURSINGASSISTANT": CredentialType.NA,
    }
    
    if normalized in credential_map:
        return credential_map[normalized]
    
    raise ValueError(
        f"Invalid credential type: '{value}'. Must be one of: RN, LPN, GNA, CNA, NA"
    )


def normalize_phone_number(value: str) -> str:
    """
    Normalize phone number to E.164 format.
    
    Examples:
        (410) 555-1234 → +14105551234
        410-555-1234 → +14105551234
        4105551234 → +14105551234
    
    Args:
        value: Raw phone number
    
    Returns:
        E.164 formatted phone number
    
    Raises:
        ValueError: Invalid phone format
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', value)
    
    # Handle US format (10 or 11 digits)
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    
    raise ValueError(
        f"Invalid phone number: '{value}'. Must be 10 digits (US format)"
    )


def normalize_license_number(value: str) -> str:
    """
    Normalize license number (uppercase, strip whitespace).
    
    Args:
        value: Raw license number
    
    Returns:
        Normalized license number
    """
    return str(value).strip().upper()


# ============================================================================
# REQUEST SCHEMAS — Caregiver Onboarding
# ============================================================================

class CaregiverRegistrationRequest(BaseModel):
    """
    Caregiver registration request with hyper-strict validation.
    
    Enforces:
    - Email format (EmailStr)
    - Phone normalization to E.164
    - License type normalization to enum
    - NPI number format (10 digits)
    - License number format
    - Minimum hourly rate (>= 0)
    """
    
    full_name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=255,
            description="Full legal name",
            examples=["Jane Smith", "John Doe RN"],
        )
    ]
    
    email: Annotated[
        EmailStr,
        Field(
            description="Valid email address",
            examples=["jane.smith@example.com"],
        )
    ]
    
    phone_number: Annotated[
        str,
        Field(
            description="US phone number (any format)",
            examples=["(410) 555-1234", "410-555-1234", "4105551234"],
        )
    ]
    
    npi_number: Annotated[
        str,
        Field(
            pattern=r"^\d{10}$",
            description="10-digit NPI number",
            examples=["1234567890"],
        )
    ]
    
    md_license_number: Annotated[
        str,
        Field(
            min_length=3,
            max_length=50,
            description="Maryland license number",
            examples=["CNA12345", "RN67890"],
        )
    ]
    
    credential_type: Annotated[
        str,
        Field(
            description="Clinical credential type (normalized to RN/LPN/GNA/CNA/NA)",
            examples=["CNA", "cna", "C.N.A.", "RN", "LPN"],
        )
    ]
    
    state: Annotated[
        str,
        Field(
            pattern=r"^[A-Z]{2}$",
            description="Two-letter state code",
            examples=["MD", "VA", "DC"],
        )
    ] = "MD"
    
    service_lines: Annotated[
        str,
        Field(
            description="Comma-separated service lines or 'ALL'",
            examples=["ALL", "HOSPITAL,URGENT_CARE", "SKILLED_NURSING"],
        )
    ] = "ALL"
    
    min_hourly_rate: Annotated[
        float,
        Field(
            ge=0.0,
            le=500.0,
            description="Minimum acceptable hourly rate",
            examples=[40.0, 50.0, 75.0],
        )
    ] = 0.0
    
    home_zip: Annotated[
        str | None,
        Field(
            pattern=r"^\d{5}$",
            description="5-digit ZIP code",
            examples=["21201", "20001"],
        )
    ] = None
    
    # Validators
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Normalize phone to E.164 format."""
        return normalize_phone_number(v)
    
    @field_validator("credential_type")
    @classmethod
    def validate_credential(cls, v: str) -> str:
        """Normalize credential type to exact enum value."""
        return normalize_credential_type(v).value
    
    @field_validator("md_license_number", "npi_number")
    @classmethod
    def validate_license_format(cls, v: str) -> str:
        """Normalize license numbers (uppercase, strip)."""
        return normalize_license_number(v)
    
    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        """Validate state is supported."""
        try:
            return USState(v.upper()).value
        except ValueError as exc:
            raise ValueError(
                f"Invalid state: '{v}'. Must be one of: {[s.value for s in USState]}"
            ) from exc
    
    @field_validator("service_lines")
    @classmethod
    def validate_service_lines(cls, v: str) -> str:
        """Validate service lines format."""
        if v.upper() == "ALL":
            return "ALL"
        
        # Validate each service line
        lines = [line.strip().upper() for line in v.split(",")]
        valid_lines = {sl.value for sl in ServiceLine}
        
        for line in lines:
            if line not in valid_lines:
                raise ValueError(
                    f"Invalid service line: '{line}'. Must be one of: {valid_lines}"
                )
        
        return ",".join(lines)
    
    model_config = {
        "str_strip_whitespace": True,
        "str_to_upper": False,  # We handle case normalization explicitly
    }


class CaregiverLoginRequest(BaseModel):
    """Caregiver login request."""
    
    email: Annotated[
        EmailStr,
        Field(description="Registered email address")
    ]
    
    password: Annotated[
        str,
        Field(
            min_length=8,
            max_length=128,
            description="Password (8-128 characters)",
        )
    ]


class TokenResponse(BaseModel):
    """JWT token response."""
    
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration in seconds")
    provider_id: UUID = Field(description="Provider UUID")


class CaregiverProfileResponse(BaseModel):
    """Caregiver profile response."""
    
    provider_id: UUID
    full_name: str
    email: str
    phone_number: str
    credential_type: CredentialType
    state: USState
    license_status: str
    min_hourly_rate: float
    service_lines: str
    dispatch_status: str
    vetted_status: str
    created_at: datetime
    
    model_config = {
        "from_attributes": True,  # Enable ORM mode
    }


# ============================================================================
# ERROR RESPONSES
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: str = Field(description="Error code")
    detail: str = Field(description="Human-readable error message")
    field: str | None = Field(default=None, description="Field that caused error")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "DUPLICATE_EMAIL",
                    "detail": "Email address already registered",
                    "field": "email",
                },
                {
                    "error": "INVALID_CREDENTIAL_TYPE",
                    "detail": "Invalid credential type: 'xyz'. Must be one of: RN, LPN, GNA, CNA, NA",
                    "field": "credential_type",
                },
            ]
        }
    }


# ============================================================================
# MARYLAND-SPECIFIC CERTIFICATION SCHEMAS — Phase 2: Integrity (Compliance)
# ============================================================================

class MarylandLicenseType(str, Enum):
    """
    Maryland Board of Nursing license types.
    
    Crucial distinction: GNA (Geriatric Nursing Assistant) is essential
    for Maryland Assisted Living facilities under COMAR regulations.
    """
    CNA = "CNA"   # Certified Nursing Assistant
    GNA = "GNA"   # Geriatric Nursing Assistant (Crucial for Assisted Living)
    LPN = "LPN"   # Licensed Practical Nurse
    RN = "RN"     # Registered Nurse


class HealthcareCredentialSchema(BaseModel):
    """
    Maryland healthcare credential validation schema.
    
    Enforces:
    - Valid Maryland license type (CNA, GNA, LPN, RN)
    - Official MBON license number
    - Future expiration date (active licenses only)
    - OHCQ registry verification status
    - Background check clearance status
    """
    
    license_type: MarylandLicenseType = Field(
        ...,
        description="Type of MD state nursing credential"
    )
    
    license_number: str = Field(
        ...,
        description="Official Maryland Board of Nursing license number"
    )
    
    expiration_date: date = Field(
        ...,
        description="Must be a future date to be active"
    )
    
    is_ohcq_verified: bool = Field(
        default=False,
        description="Has this passed the OHCQ registry verification check?"
    )
    
    background_check_passed: bool = Field(
        default=False,
        description="Criminal background screening status"
    )
    
    @field_validator("expiration_date")
    @classmethod
    def check_expiration(cls, v: date) -> date:
        """
        Validate license expiration date is in the future.
        
        Args:
            v: Expiration date to validate
        
        Returns:
            Validated expiration date
        
        Raises:
            ValueError: If license has expired
        """
        if v < date.today():
            raise ValueError("License has expired. Cannot authorize candidate for matching.")
        return v

    model_config = {
        "from_attributes": True,
    }
