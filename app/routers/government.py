"""
VettedMe Government API - Phase 3: Zero-Knowledge Clearance Verification

This router provides privacy-preserving verification for:
- Security clearances (Confidential, Secret, Top Secret, TS/SCI)
- Cybersecurity certifications (CISSP, Security+, CEH, CISM)
- Government credentials (PIV, CAC)
- Public trust positions

Key Innovation: ZERO-KNOWLEDGE PROOFS
- Contractor NEVER sees raw PII
- Worker controls data disclosure
- VettedMe provides cryptographic attestation
- Removes data liability from contractor servers

Perfect For:
- Defense contractors (ITAR/FedRAMP compliant)
- Platform integrations (Deel, Upwork, ADP, Okta)
- Payroll systems (verify without storing)
- Enterprise HR (zero-trust architecture)

Pricing: $0.15 per verification (vs $100+ traditional clearance checks)
Speed: < 2 seconds (vs weeks for traditional DCSA checks)

Status: PLANNED (Q1 2027 launch)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.services.government_verification import (
    GovernmentVerificationEngine,
    ClearanceVerificationPayload,
    ZeroKnowledgeProof,
    CISSPVerificationPayload,
    SecurityPlusPayload
)
from app.services.credential_industries import get_industry_config

router = APIRouter(
    prefix="/api/v1/government",
    tags=["Phase 3 - Government & Enterprise Zero-Knowledge Verification"]
)


@router.post(
    "/verify/clearance/zkp",
    response_model=ZeroKnowledgeProof,
    summary="🔒 Zero-Knowledge Security Clearance Attestation",
    description="""
    **Phase 3: Coming Soon (Q1 2027)**
    
    **THE KILLER FEATURE** - Removes data liability from contractors.
    
    **The Problem:**
    Defense contractors can't store clearance data on their servers:
    - ITAR restrictions (no export of clearance info)
    - FedRAMP compliance (no PII on cloud servers)
    - NISPOM requirements (proper classified access handling)
    - Security policy (minimize data breach risk)
    
    **The Traditional Solution:**
    Manual clearance verification:
    - Call government security office ($100+ per check)
    - Wait weeks for response
    - Still creates data liability if they record it
    
    **The VettedMe Solution:**
    Zero-knowledge proof attestation:
    1. Worker provides hashed identity (SHA256 of SSN + DOB)
    2. VettedMe queries DCSA/OPM using internal mapping
    3. VettedMe generates cryptographically signed attestation
    4. Contractor receives proof WITHOUT seeing raw PII
    
    **What Contractor Receives:**
    - "SECRET clearance: CONFIRMED ✓"
    - Cryptographic signature (tamper-proof)
    - Validity status (ACTIVE/EXPIRED)
    - Verification token (audit trail)
    
    **What Contractor NEVER Sees:**
    - Raw SSN
    - Investigation details
    - Granting agency
    - Exact clearance date
    
    **Legal Benefits:**
    - ITAR compliant (no clearance data export)
    - FedRAMP ready (no PII on contractor servers)
    - NISPOM compliant (proper handling)
    - Zero data breach liability
    
    **Example Use Cases:**
    - Upwork: "Verify this contractor has Top Secret clearance"
    - Deel: "Verify before hiring for DoD project"
    - ADP: "Verify for payroll compliance"
    - Defense contractor: "Verify without storing clearance data"
    """
)
async def verify_clearance_zkp(
    payload: ClearanceVerificationPayload,
    db: Session = Depends(get_db)
) -> ZeroKnowledgeProof:
    """
    Execute zero-knowledge clearance attestation.
    
    Args:
        payload: Clearance verification request with hashed identity
        db: Database session
        
    Returns:
        Zero-knowledge proof with cryptographic signature
    """
    try:
        engine = GovernmentVerificationEngine(db)
        proof = engine.execute_zkp_clearance_attestation(payload)
        
        return proof
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Zero-knowledge attestation failed: {str(e)}"
        )


@router.post(
    "/verify/cissp",
    summary="Verify CISSP Certification",
    description="""
    **Phase 3: Coming Soon (Q1 2027)**
    
    Verify CISSP (Certified Information Systems Security Professional).
    
    **CISSP is the Gold Standard:**
    - Most respected cybersecurity certification
    - Required 5 years experience or 4 years + degree
    - Rigorous 6-hour exam (250 questions)
    - 40 CPEs required annually
    - DoD 8570 compliant (IAT Level III, IAM Level II)
    
    **Market Value:**
    - Average salary: $120,000-$180,000
    - Required for many government IT security positions
    - Highly valued by defense contractors
    
    **What We Verify:**
    - Certification is active (not expired)
    - CPE credits are current
    - Endorsement complete
    - Good standing with (ISC)²
    - DoD 8570 compliance status
    """
)
async def verify_cissp(
    payload: CISSPVerificationPayload,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify CISSP certification.
    
    Args:
        payload: CISSP verification request
        db: Database session
        
    Returns:
        Certification verification result
    """
    try:
        engine = GovernmentVerificationEngine(db)
        result = engine.verify_cissp_certification(payload)
        
        return {
            "success": True,
            "verification": result,
            "credential_type": "CISSP",
            "industry": "GOVERNMENT_ENTERPRISE",
            "pricing": {
                "vettedme_cost": "$0.15",
                "traditional_cost": "$0 (but manual verification takes hours)",
                "value": "Instant cryptographic proof vs manual checking"
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CISSP verification failed: {str(e)}"
        )


@router.post(
    "/verify/security-plus",
    summary="Verify CompTIA Security+",
    description="""
    **Phase 3: Coming Soon (Q1 2027)**
    
    Verify CompTIA Security+ certification.
    
    **Security+ is DoD 8570 Baseline:**
    - Required for 95% of DoD IT positions
    - Entry-level but widely respected
    - DoD 8570 compliant (IAT Level II, IAM Level I)
    - Renewable every 3 years via CEUs
    
    **Perfect For:**
    - Government IT contractors
    - DoD system administrators
    - Entry-level cybersecurity professionals
    - Security operations center (SOC) analysts
    """
)
async def verify_security_plus(
    payload: SecurityPlusPayload,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify Security+ certification.
    
    Args:
        payload: Security+ verification request
        db: Database session
        
    Returns:
        Certification verification result
    """
    try:
        engine = GovernmentVerificationEngine(db)
        result = engine.verify_security_plus_certification(payload)
        
        return {
            "success": True,
            "verification": result,
            "credential_type": "SECURITY_PLUS",
            "industry": "GOVERNMENT_ENTERPRISE",
            "dod_8570_compliant": result.get("dod_8570_compliant")
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security+ verification failed: {str(e)}"
        )


@router.get(
    "/status",
    summary="Get Phase 3 (Government/Enterprise) Status",
    description="""
    Get the current status of Phase 3 government verification.
    
    Shows:
    - Launch date (Q1 2027)
    - Supported credentials
    - Zero-knowledge proof architecture
    - Platform integration capabilities
    - Pricing
    """
)
async def get_government_status() -> Dict[str, Any]:
    """
    Get Phase 3 government verification status.
    
    Returns:
        Status, roadmap, and capabilities
    """
    gov_config = get_industry_config("GOVERNMENT_ENTERPRISE")
    
    return {
        "phase": "Phase 3",
        "status": gov_config.status if gov_config else "PLANNED",
        "target_launch_date": gov_config.target_launch_date if gov_config else "2027-03-31",
        "key_innovation": "ZERO-KNOWLEDGE PROOFS",
        "value_proposition": {
            "problem": "Defense contractors can't store clearance data (ITAR/FedRAMP/NISPOM)",
            "solution": "Worker carries VettedMe Passport. Contractor verifies with ZKP. Zero liability.",
            "benefit": "Removes data liability + instant verification + cryptographic proof"
        },
        "supported_credentials": [
            {
                "type": "Security Clearances",
                "levels": ["Confidential", "Secret", "Top Secret", "TS/SCI"],
                "method": "Zero-Knowledge Proof Attestation"
            },
            {
                "type": "Cybersecurity Certifications",
                "certs": ["CISSP", "CISM", "CEH", "Security+", "GSEC"],
                "method": "Direct API Verification"
            },
            {
                "type": "Government Credentials",
                "creds": ["PIV", "CAC", "Public Trust"],
                "method": "PKI Certificate Validation"
            }
        ],
        "pricing": {
            "per_verification": "$0.15",
            "traditional_comparison": "$100+ (manual clearance check)",
            "savings": "99.85%",
            "speed": "< 2 seconds vs weeks"
        },
        "platform_integrations": {
            "ready_for": ["Upwork", "Toptal", "Deel", "ADP", "Gusto", "Okta", "Auth0"],
            "integration_type": "REST API + SDK (Python, TypeScript, Java)",
            "white_label_available": True
        },
        "technical_architecture": {
            "zkp_method": "Ed25519 signatures + selective disclosure",
            "privacy_guarantees": ["No PII disclosure", "Worker data sovereignty", "Contractor zero liability"],
            "compliance": ["ITAR", "FedRAMP", "NISPOM", "DoD 8570"]
        },
        "api_endpoints": {
            "clearance_zkp": "/api/v1/government/verify/clearance/zkp",
            "cissp": "/api/v1/government/verify/cissp",
            "security_plus": "/api/v1/government/verify/security-plus"
        },
        "first_client_goal": "Win Upwork or Deel integration → unlock network effects"
    }


@router.get(
    "/demo/zkp",
    summary="Get Zero-Knowledge Proof Demo",
    description="""
    Demonstration of zero-knowledge proof architecture.
    
    Shows:
    - How hashed identity works
    - What contractor receives vs what worker controls
    - Cryptographic signature format
    - Audit trail structure
    """
)
async def get_zkp_demo() -> Dict[str, Any]:
    """
    Get zero-knowledge proof demonstration.
    
    Returns:
        Demo data showing ZKP architecture
    """
    return {
        "scenario": "Defense contractor hiring for Top Secret project",
        "traditional_process": {
            "step_1": "Request SSN from worker",
            "step_2": "Call DCSA security office ($100+)",
            "step_3": "Wait 2-4 weeks for response",
            "step_4": "Store clearance data on contractor server",
            "problems": [
                "Data liability on contractor",
                "Slow (weeks)",
                "Expensive ($100+)",
                "Security risk (data breach exposure)"
            ]
        },
        "vettedme_zkp_process": {
            "step_1": "Worker creates VettedMe Passport (one-time)",
            "step_2": "Worker adds clearance badge (VettedMe verifies with DCSA)",
            "step_3": "Contractor requests verification via API",
            "step_4": "VettedMe returns zero-knowledge proof",
            "benefits": [
                "Zero data liability for contractor",
                "Instant (< 2 seconds)",
                "Cheap ($0.15)",
                "Zero security risk (contractor stores nothing)"
            ]
        },
        "example_request": {
            "hashed_ssn_identity": "a3f5b8c9d2e1f4a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
            "clearance_level_requested": "TOP_SECRET",
            "requesting_organization": "Acme Defense Contractors LLC"
        },
        "example_response": {
            "attestation_signature": "ZKP-SIG-DOD-VERIFIED-0x7F9BC3A1D8E4F2B6",
            "clearance_level_confirmed": "TOP_SECRET",
            "proof_valid": True,
            "data_liability_retained": "USER_SOVEREIGN",
            "verified_at": "2027-01-15T14:30:00Z",
            "expires_at": "2027-04-15T14:30:00Z",
            "verification_token": "gov_vtok_1705328400_TOP_SECRET_a3f5b8c9_X7k9mQ2pL5wR"
        },
        "what_contractor_never_sees": [
            "Raw SSN",
            "Date of birth",
            "Investigation date",
            "Granting agency (CIA, NSA, DoD, etc.)",
            "Poly status",
            "Investigation type (T5, T3, etc.)"
        ],
        "what_contractor_does_see": [
            "Clearance level confirmed (YES/NO)",
            "Validity status (ACTIVE/EXPIRED)",
            "Cryptographic signature (tamper-proof)",
            "Verification timestamp",
            "Audit trail token"
        ],
        "legal_compliance": {
            "ITAR": "No clearance data exported from government systems",
            "FedRAMP": "No PII stored on contractor cloud servers",
            "NISPOM": "Proper handling of classified access information",
            "Zero_Trust": "Never trust, always verify (but don't store)"
        }
    }
