"""
VettedMe - Industry-Agnostic Credential Verification System

This module defines the credential infrastructure for all target industries:
- Phase 1: Healthcare & Clinical Staffing (Maryland MBON/OHCQ)
- Phase 2: Commercial Transportation, Logistics & HazMat (DOT/MVA)
- Phase 3: Government Contracting & Cybersecurity (Federal/State clearances)

Architecture:
- Each industry has specific credential types with unique verification sources
- Unified verification API works across all industries
- Extensible for future industry expansion
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field


# ============================================================================
# Industry Definitions
# ============================================================================

class Industry(str, Enum):
    """Supported industries for credential verification"""
    HEALTHCARE = "healthcare"
    LOGISTICS = "logistics"
    GOVERNMENT = "government"
    GENERAL = "general"


# ============================================================================
# Healthcare Credentials (Phase 1 - Current Focus)
# ============================================================================

class HealthcareCredentialType(str, Enum):
    """Healthcare professional credentials"""
    # Nursing Credentials
    RN = "RN"  # Registered Nurse
    LPN = "LPN"  # Licensed Practical Nurse
    CNA = "CNA"  # Certified Nursing Assistant
    GNA = "GNA"  # Geriatric Nursing Assistant
    
    # Advanced Practice
    NP = "NP"  # Nurse Practitioner
    CNS = "CNS"  # Clinical Nurse Specialist
    CRNA = "CRNA"  # Certified Registered Nurse Anesthetist
    
    # Allied Health
    RT = "RT"  # Respiratory Therapist
    PT = "PT"  # Physical Therapist
    OT = "OT"  # Occupational Therapist
    SLP = "SLP"  # Speech-Language Pathologist
    
    # Physicians
    MD = "MD"  # Medical Doctor
    DO = "DO"  # Doctor of Osteopathic Medicine


class HealthcareVerificationSource(str, Enum):
    """Sources for healthcare credential verification"""
    MBON = "MBON"  # Maryland Board of Nursing
    NCSBN = "NCSBN"  # National Council of State Boards of Nursing
    NPDB = "NPDB"  # National Practitioner Data Bank
    OIG = "OIG"  # Office of Inspector General (exclusions)
    SAM_GOV = "SAM_GOV"  # System for Award Management
    STATE_BOARD = "STATE_BOARD"  # State-specific licensing boards


# ============================================================================
# Logistics & Transportation Credentials (Phase 2 - Next)
# ============================================================================

class LogisticsCredentialType(str, Enum):
    """Commercial transportation credentials"""
    # CDL Classes
    CDL_CLASS_A = "CDL_CLASS_A"  # Tractor-trailers, truck and trailer combinations
    CDL_CLASS_B = "CDL_CLASS_B"  # Straight trucks, large buses
    CDL_CLASS_C = "CDL_CLASS_C"  # Small HazMat vehicles
    
    # CDL Endorsements
    HAZMAT = "HAZMAT"  # Hazardous materials
    TANKER = "TANKER"  # Tank vehicles
    DOUBLES_TRIPLES = "DOUBLES_TRIPLES"  # Double/triple trailers
    PASSENGER = "PASSENGER"  # Passenger vehicles
    SCHOOL_BUS = "SCHOOL_BUS"  # School bus
    
    # Medical Certifications
    DOT_MEDICAL = "DOT_MEDICAL"  # DOT medical examiner certificate
    TWIC = "TWIC"  # Transportation Worker Identification Credential
    
    # Safety Certifications
    DEFENSIVE_DRIVING = "DEFENSIVE_DRIVING"
    FORKLIFT = "FORKLIFT"
    OSHA_SAFETY = "OSHA_SAFETY"


class LogisticsVerificationSource(str, Enum):
    """Sources for logistics credential verification"""
    MVA = "MVA"  # Motor Vehicle Administration (state-specific)
    FMCSA = "FMCSA"  # Federal Motor Carrier Safety Administration
    DOT = "DOT"  # Department of Transportation
    TSA = "TSA"  # Transportation Security Administration (TWIC)
    CDLIS = "CDLIS"  # Commercial Driver's License Information System


# ============================================================================
# Government & Cybersecurity Credentials (Phase 3 - Enterprise)
# ============================================================================

class GovernmentCredentialType(str, Enum):
    """Government contracting and security clearances"""
    # Security Clearances
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"
    TOP_SECRET = "TOP_SECRET"
    TS_SCI = "TS_SCI"  # Top Secret/Sensitive Compartmented Information
    
    # Public Trust
    PUBLIC_TRUST = "PUBLIC_TRUST"
    HIGH_RISK_PUBLIC_TRUST = "HIGH_RISK_PUBLIC_TRUST"
    
    # Cybersecurity Certifications
    CISSP = "CISSP"  # Certified Information Systems Security Professional
    CISM = "CISM"  # Certified Information Security Manager
    CEH = "CEH"  # Certified Ethical Hacker
    COMPTIA_SECURITY_PLUS = "COMPTIA_SECURITY_PLUS"
    
    # Government Credentials
    PIV = "PIV"  # Personal Identity Verification
    CAC = "CAC"  # Common Access Card


class GovernmentVerificationSource(str, Enum):
    """Sources for government credential verification"""
    OPM = "OPM"  # Office of Personnel Management
    DCSA = "DCSA"  # Defense Counterintelligence and Security Agency
    GSA = "GSA"  # General Services Administration
    E_VERIFY = "E_VERIFY"  # Employment eligibility verification
    SAM_GOV = "SAM_GOV"  # System for Award Management


# ============================================================================
# Unified Credential Model
# ============================================================================

class CredentialDefinition(BaseModel):
    """Industry-agnostic credential definition"""
    credential_type: str
    credential_display_name: str
    industry: Industry
    verification_sources: List[str]
    requires_renewal: bool
    typical_validity_period_days: Optional[int] = None
    requires_biometric: bool = False
    requires_background_check: bool = False
    legal_mandate_states: List[str] = []  # States where this credential is legally mandated
    
    class Config:
        use_enum_values = True


# ============================================================================
# Credential Registry
# ============================================================================

CREDENTIAL_REGISTRY: Dict[str, CredentialDefinition] = {
    # ========================================================================
    # PHASE 1: HEALTHCARE (Current Focus - Maryland)
    # ========================================================================
    "RN": CredentialDefinition(
        credential_type="RN",
        credential_display_name="Registered Nurse",
        industry=Industry.HEALTHCARE,
        verification_sources=[
            HealthcareVerificationSource.MBON,
            HealthcareVerificationSource.NCSBN,
            HealthcareVerificationSource.OIG
        ],
        requires_renewal=True,
        typical_validity_period_days=730,  # 2 years
        requires_biometric=True,
        requires_background_check=True,
        legal_mandate_states=["MD", "VA", "DC", "PA", "DE", "NJ"]
    ),
    "LPN": CredentialDefinition(
        credential_type="LPN",
        credential_display_name="Licensed Practical Nurse",
        industry=Industry.HEALTHCARE,
        verification_sources=[
            HealthcareVerificationSource.MBON,
            HealthcareVerificationSource.NCSBN,
            HealthcareVerificationSource.OIG
        ],
        requires_renewal=True,
        typical_validity_period_days=730,
        requires_biometric=True,
        requires_background_check=True,
        legal_mandate_states=["MD", "VA", "DC", "PA", "DE", "NJ"]
    ),
    "CNA": CredentialDefinition(
        credential_type="CNA",
        credential_display_name="Certified Nursing Assistant",
        industry=Industry.HEALTHCARE,
        verification_sources=[
            HealthcareVerificationSource.MBON,
            HealthcareVerificationSource.STATE_BOARD
        ],
        requires_renewal=True,
        typical_validity_period_days=730,
        requires_biometric=True,
        requires_background_check=True,
        legal_mandate_states=["MD", "VA", "DC", "PA", "DE", "NJ", "NY", "NC", "SC", "GA", "FL"]
    ),
    
    # ========================================================================
    # PHASE 2: LOGISTICS & TRANSPORTATION (Coming Soon)
    # ========================================================================
    "CDL_CLASS_A": CredentialDefinition(
        credential_type="CDL_CLASS_A",
        credential_display_name="CDL Class A - Tractor Trailers",
        industry=Industry.LOGISTICS,
        verification_sources=[
            LogisticsVerificationSource.MVA,
            LogisticsVerificationSource.FMCSA,
            LogisticsVerificationSource.CDLIS
        ],
        requires_renewal=True,
        typical_validity_period_days=1825,  # 5 years (varies by state)
        requires_biometric=False,
        requires_background_check=True,
        legal_mandate_states=["MD", "VA", "DC", "PA", "DE", "NJ", "NY", "NC", "SC", "GA", "FL", "TX", "CA"]
    ),
    "HAZMAT": CredentialDefinition(
        credential_type="HAZMAT",
        credential_display_name="HazMat Endorsement",
        industry=Industry.LOGISTICS,
        verification_sources=[
            LogisticsVerificationSource.MVA,
            LogisticsVerificationSource.TSA,
            LogisticsVerificationSource.FMCSA
        ],
        requires_renewal=True,
        typical_validity_period_days=1825,  # 5 years
        requires_biometric=True,  # TSA fingerprinting required
        requires_background_check=True,
        legal_mandate_states=["ALL"]  # Federal mandate
    ),
    "DOT_MEDICAL": CredentialDefinition(
        credential_type="DOT_MEDICAL",
        credential_display_name="DOT Medical Examiner Certificate",
        industry=Industry.LOGISTICS,
        verification_sources=[
            LogisticsVerificationSource.FMCSA,
            LogisticsVerificationSource.DOT
        ],
        requires_renewal=True,
        typical_validity_period_days=730,  # 2 years (max), can be shorter
        requires_biometric=False,
        requires_background_check=False,
        legal_mandate_states=["ALL"]  # Federal mandate for commercial drivers
    ),
    
    # ========================================================================
    # PHASE 3: GOVERNMENT & CYBERSECURITY (Enterprise B2B)
    # ========================================================================
    "SECRET": CredentialDefinition(
        credential_type="SECRET",
        credential_display_name="Secret Security Clearance",
        industry=Industry.GOVERNMENT,
        verification_sources=[
            GovernmentVerificationSource.DCSA,
            GovernmentVerificationSource.OPM
        ],
        requires_renewal=True,
        typical_validity_period_days=3650,  # 10 years
        requires_biometric=True,
        requires_background_check=True,
        legal_mandate_states=["ALL"]  # Federal mandate
    ),
    "TOP_SECRET": CredentialDefinition(
        credential_type="TOP_SECRET",
        credential_display_name="Top Secret Security Clearance",
        industry=Industry.GOVERNMENT,
        verification_sources=[
            GovernmentVerificationSource.DCSA,
            GovernmentVerificationSource.OPM
        ],
        requires_renewal=True,
        typical_validity_period_days=1825,  # 5 years
        requires_biometric=True,
        requires_background_check=True,
        legal_mandate_states=["ALL"]  # Federal mandate
    ),
    "CISSP": CredentialDefinition(
        credential_type="CISSP",
        credential_display_name="Certified Information Systems Security Professional",
        industry=Industry.GOVERNMENT,
        verification_sources=["ISC2"],  # (ISC)² verification
        requires_renewal=True,
        typical_validity_period_days=1095,  # 3 years
        requires_biometric=False,
        requires_background_check=False,
        legal_mandate_states=[]  # Not legally mandated, but industry standard
    ),
}


# ============================================================================
# Verification Status Model
# ============================================================================

class VerificationStatus(str, Enum):
    """Credential verification status"""
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    PENDING = "PENDING"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


class CredentialVerificationResult(BaseModel):
    """Result of a credential verification check"""
    credential_type: str
    industry: Industry
    verification_source: str
    status: VerificationStatus
    verified_at: datetime
    expires_at: Optional[datetime] = None
    license_number: Optional[str] = None
    issuing_state: Optional[str] = None
    holder_name: Optional[str] = None
    additional_data: Dict = Field(default_factory=dict)
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)
    
    class Config:
        use_enum_values = True


# ============================================================================
# Industry-Specific Verification Engines
# ============================================================================

def get_credential_definition(credential_type: str) -> Optional[CredentialDefinition]:
    """Get credential definition by type"""
    return CREDENTIAL_REGISTRY.get(credential_type)


def get_credentials_by_industry(industry: Industry) -> List[CredentialDefinition]:
    """Get all credentials for a specific industry"""
    return [
        cred for cred in CREDENTIAL_REGISTRY.values()
        if cred.industry == industry
    ]


def is_credential_mandated_in_state(credential_type: str, state: str) -> bool:
    """Check if a credential is legally mandated in a given state"""
    cred_def = get_credential_definition(credential_type)
    if not cred_def:
        return False
    
    return state in cred_def.legal_mandate_states or "ALL" in cred_def.legal_mandate_states


def estimate_credential_expiration(credential_type: str, issued_at: datetime) -> Optional[datetime]:
    """Estimate when a credential will expire based on typical validity period"""
    cred_def = get_credential_definition(credential_type)
    if not cred_def or not cred_def.typical_validity_period_days:
        return None
    
    return issued_at + timedelta(days=cred_def.typical_validity_period_days)


# ============================================================================
# Global Industry Configuration Registry
# ============================================================================

class IndustryConfig(BaseModel):
    """Configuration for each industry vertical"""
    name: str
    base_query_cost: float
    verification_methods: List[str]
    status: str = "LIVE"  # LIVE, COMING_SOON, PLANNED
    target_launch_date: Optional[str] = None


# Global Registry defining the Industry-Agnostic Passport footprint
INDUSTRY_CONFIG_REGISTRY: Dict[str, IndustryConfig] = {
    "HEALTHCARE": IndustryConfig(
        name="Healthcare Clinical Registry",
        base_query_cost=0.07,
        verification_methods=["MBON_SCRAPER", "OIG_EXCLUSION_CHECK", "JUDICIARY_BACKGROUND", "NCSBN_API"],
        status="LIVE",
        target_launch_date="2026-09-30"
    ),
    "LOGISTICS": IndustryConfig(
        name="Logistics & Commercial Transport",
        base_query_cost=0.07,
        verification_methods=["MVA_CDL_VERIFY", "FMCSA_SAFETY_RECORD", "HAZMAT_ENDORSEMENT", "DOT_MEDICAL_CERT"],
        status="COMING_SOON",
        target_launch_date="2026-12-31"
    ),
    "GOVERNMENT_ENTERPRISE": IndustryConfig(
        name="Federal Government & Enterprise Systems",
        base_query_cost=0.15,
        verification_methods=["DOD_CLEARANCE_PASSTHROUGH", "CISSP_CREDENTIAL_API", "ZERO_KNOWLEDGE_PROOF", "DCSA_API"],
        status="PLANNED",
        target_launch_date="2027-03-31"
    )
}


# Legacy pricing dict for backward compatibility
VERIFICATION_PRICING: Dict[Industry, float] = {
    Industry.HEALTHCARE: 0.07,
    Industry.LOGISTICS: 0.07,
    Industry.GOVERNMENT: 0.15,
    Industry.GENERAL: 0.05,
}


def get_verification_price(industry: Industry) -> float:
    """Get the price per verification for an industry"""
    return VERIFICATION_PRICING.get(industry, 0.07)


def get_industry_config(industry_key: str) -> Optional[IndustryConfig]:
    """Get industry configuration by key"""
    return INDUSTRY_CONFIG_REGISTRY.get(industry_key)


# ============================================================================
# Roadmap Visibility
# ============================================================================

INDUSTRY_ROADMAP = {
    "Phase 1 - Healthcare": {
        "status": "LIVE",
        "target_states": ["MD", "VA", "DC", "PA", "DE"],
        "target_date": "2026-09-30",
        "credentials": ["RN", "LPN", "CNA", "GNA"],
        "value_prop": "Cut onboarding from 2 weeks to 2 minutes",
        "first_client_goal": "PG County staffing agency"
    },
    "Phase 2 - Logistics": {
        "status": "COMING_SOON",
        "target_states": ["MD", "VA", "DC", "PA", "DE", "NJ"],
        "target_date": "2026-12-31",
        "credentials": ["CDL_CLASS_A", "HAZMAT", "DOT_MEDICAL"],
        "value_prop": "Instant DOT compliance verification for transport hubs",
        "first_client_goal": "Regional logistics network"
    },
    "Phase 3 - Enterprise APIs": {
        "status": "PLANNED",
        "target_states": ["ALL"],
        "target_date": "2027-03-31",
        "credentials": ["SECRET", "TOP_SECRET", "CISSP", "PIV"],
        "value_prop": "Universal trust layer for B2B platforms (Upwork, Deel, ADP)",
        "first_client_goal": "Federal contractor or staffing software integration"
    }
}


def get_industry_roadmap():
    """Return the full industry expansion roadmap for display"""
    return INDUSTRY_ROADMAP
