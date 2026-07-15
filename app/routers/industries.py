"""
VettedMe Industries API - Multi-Industry Capability Discovery

This endpoint allows external platforms to discover:
- Which industries VettedMe supports
- What credentials are available per industry
- Pricing for each industry
- Verification methods and data sources
- Roadmap status (LIVE, COMING_SOON, PLANNED)

Use Case:
- Platform integration partners (Upwork, Deel, etc.) query capabilities
- Employers check if their industry is supported
- Sales prospects see roadmap and pricing
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
from pydantic import BaseModel

from app.services.credential_industries import (
    INDUSTRY_CONFIG_REGISTRY,
    CREDENTIAL_REGISTRY,
    INDUSTRY_ROADMAP,
    Industry,
    get_credentials_by_industry,
    get_industry_config,
    get_verification_price
)

router = APIRouter(
    prefix="/api/v1/industries",
    tags=["Multi-Industry Discovery"]
)


class IndustryCapabilityResponse(BaseModel):
    """Response showing VettedMe's multi-industry capabilities"""
    industry_key: str
    industry_name: str
    status: str
    base_query_cost: float
    verification_methods: List[str]
    supported_credentials: List[Dict[str, Any]]
    target_launch_date: str | None
    
    class Config:
        json_schema_extra = {
            "example": {
                "industry_key": "HEALTHCARE",
                "industry_name": "Healthcare Clinical Registry",
                "status": "LIVE",
                "base_query_cost": 0.07,
                "verification_methods": ["MBON_SCRAPER", "OIG_EXCLUSION_CHECK"],
                "supported_credentials": [
                    {
                        "credential_type": "RN",
                        "display_name": "Registered Nurse",
                        "requires_biometric": True,
                        "typical_validity_days": 730
                    }
                ],
                "target_launch_date": "2026-09-30"
            }
        }


class IndustryRoadmapResponse(BaseModel):
    """Full roadmap showing all phases"""
    total_industries: int
    live_count: int
    coming_soon_count: int
    planned_count: int
    industries: List[IndustryCapabilityResponse]
    roadmap_phases: Dict[str, Any]


@router.get(
    "/capabilities",
    response_model=IndustryRoadmapResponse,
    summary="Get all industry capabilities and roadmap",
    description="""
    Returns VettedMe's complete multi-industry capability matrix.
    
    **Use Cases:**
    - Platform integration partners discover supported industries
    - Sales prospects see roadmap and pricing
    - Developers check available verification methods
    
    **Returns:**
    - All industries (Healthcare, Logistics, Government)
    - Status of each (LIVE, COMING_SOON, PLANNED)
    - Pricing per industry
    - Available credentials and verification methods
    """
)
async def get_industry_capabilities():
    """
    Get complete industry capability matrix.
    
    Shows what VettedMe can verify across all industries.
    """
    industries_list = []
    live_count = 0
    coming_soon_count = 0
    planned_count = 0
    
    for industry_key, config in INDUSTRY_CONFIG_REGISTRY.items():
        # Count by status
        if config.status == "LIVE":
            live_count += 1
        elif config.status == "COMING_SOON":
            coming_soon_count += 1
        elif config.status == "PLANNED":
            planned_count += 1
        
        # Get credentials for this industry
        industry_enum = None
        if industry_key == "HEALTHCARE":
            industry_enum = Industry.HEALTHCARE
        elif industry_key == "LOGISTICS":
            industry_enum = Industry.LOGISTICS
        elif industry_key == "GOVERNMENT_ENTERPRISE":
            industry_enum = Industry.GOVERNMENT
        
        credentials = []
        if industry_enum:
            creds = get_credentials_by_industry(industry_enum)
            credentials = [
                {
                    "credential_type": cred.credential_type,
                    "display_name": cred.credential_display_name,
                    "requires_biometric": cred.requires_biometric,
                    "requires_background_check": cred.requires_background_check,
                    "typical_validity_days": cred.typical_validity_period_days,
                    "legal_mandate_states": cred.legal_mandate_states
                }
                for cred in creds
            ]
        
        industries_list.append(IndustryCapabilityResponse(
            industry_key=industry_key,
            industry_name=config.name,
            status=config.status,
            base_query_cost=config.base_query_cost,
            verification_methods=config.verification_methods,
            supported_credentials=credentials,
            target_launch_date=config.target_launch_date
        ))
    
    return IndustryRoadmapResponse(
        total_industries=len(INDUSTRY_CONFIG_REGISTRY),
        live_count=live_count,
        coming_soon_count=coming_soon_count,
        planned_count=planned_count,
        industries=industries_list,
        roadmap_phases=INDUSTRY_ROADMAP
    )


@router.get(
    "/capabilities/{industry_key}",
    response_model=IndustryCapabilityResponse,
    summary="Get capabilities for a specific industry",
    description="""
    Returns detailed capabilities for a single industry.
    
    **Industry Keys:**
    - `HEALTHCARE` - Clinical staffing (RN, LPN, CNA)
    - `LOGISTICS` - Commercial transport (CDL, HazMat)
    - `GOVERNMENT_ENTERPRISE` - Federal contractors (Clearances, CISSP)
    """
)
async def get_industry_capability(industry_key: str):
    """
    Get detailed capabilities for a specific industry.
    
    Args:
        industry_key: One of HEALTHCARE, LOGISTICS, GOVERNMENT_ENTERPRISE
    
    Returns:
        Industry capabilities including pricing, methods, and credentials
    """
    industry_key = industry_key.upper()
    
    config = get_industry_config(industry_key)
    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Industry '{industry_key}' not found. Valid keys: HEALTHCARE, LOGISTICS, GOVERNMENT_ENTERPRISE"
        )
    
    # Get credentials for this industry
    industry_enum = None
    if industry_key == "HEALTHCARE":
        industry_enum = Industry.HEALTHCARE
    elif industry_key == "LOGISTICS":
        industry_enum = Industry.LOGISTICS
    elif industry_key == "GOVERNMENT_ENTERPRISE":
        industry_enum = Industry.GOVERNMENT
    
    credentials = []
    if industry_enum:
        creds = get_credentials_by_industry(industry_enum)
        credentials = [
            {
                "credential_type": cred.credential_type,
                "display_name": cred.credential_display_name,
                "requires_biometric": cred.requires_biometric,
                "requires_background_check": cred.requires_background_check,
                "typical_validity_days": cred.typical_validity_period_days,
                "legal_mandate_states": cred.legal_mandate_states
            }
            for cred in creds
        ]
    
    return IndustryCapabilityResponse(
        industry_key=industry_key,
        industry_name=config.name,
        status=config.status,
        base_query_cost=config.base_query_cost,
        verification_methods=config.verification_methods,
        supported_credentials=credentials,
        target_launch_date=config.target_launch_date
    )


@router.get(
    "/pricing",
    summary="Get pricing matrix across all industries",
    description="""
    Returns the pricing for credential verification across all industries.
    
    **Pricing Model:**
    - Healthcare: $0.07/verification (vs $50+ traditional)
    - Logistics: $0.07/verification (vs $30+ MVA checks)
    - Government: $0.15/verification (vs $100+ clearance checks)
    
    **Value Proposition:**
    - 100x cheaper than traditional background checks
    - < 1 second verification time
    - Cryptographically secure
    """
)
async def get_pricing_matrix():
    """
    Get pricing for all industries.
    
    Shows the cost advantage of VettedMe vs traditional verification.
    """
    pricing_matrix = []
    
    for industry_key, config in INDUSTRY_CONFIG_REGISTRY.items():
        pricing_matrix.append({
            "industry": config.name,
            "vettedme_price": f"${config.base_query_cost:.2f}",
            "traditional_price": {
                "HEALTHCARE": "$50+",
                "LOGISTICS": "$30+",
                "GOVERNMENT_ENTERPRISE": "$100+"
            }.get(industry_key, "N/A"),
            "savings": f"{int((1 - config.base_query_cost / 50) * 100)}%+",
            "response_time": "< 1 second",
            "status": config.status
        })
    
    return {
        "pricing": pricing_matrix,
        "volume_discounts": {
            "1-1000_verifications": "Standard rate",
            "1001-10000_verifications": "5% discount",
            "10001-50000_verifications": "10% discount",
            "50001+_verifications": "Custom enterprise pricing"
        },
        "enterprise_options": [
            "Dedicated API endpoints",
            "Custom SLA (99.99% uptime)",
            "White-label options",
            "On-premise deployment available"
        ]
    }


@router.get(
    "/roadmap",
    summary="Get product roadmap and launch timeline",
    description="""
    Returns the full VettedMe product roadmap showing:
    - Phase 1: Healthcare (LIVE)
    - Phase 2: Logistics (Coming Soon - Dec 2026)
    - Phase 3: Enterprise APIs (Planned - Q1 2027)
    
    **Strategic Vision:**
    - Healthcare proves the operational model
    - Logistics establishes horizontal scalability
    - Enterprise APIs unlock network effects
    """
)
async def get_roadmap():
    """
    Get the full product roadmap.
    
    Shows the strategic expansion from healthcare → logistics → enterprise.
    """
    return {
        "roadmap": INDUSTRY_ROADMAP,
        "current_focus": "Phase 1 - Healthcare",
        "next_milestone": "Phase 2 - Logistics (Dec 2026)",
        "vision": "The Universal Trust Layer for the Modern Economy",
        "exit_strategy": "Become infrastructure layer (like Plaid for banking)"
    }
