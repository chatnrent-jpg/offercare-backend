"""
Shift Scheduling & Automated Matching API
Phase 2: Intelligence & Compliance - Workforce Optimization

Exposes OHCQ-compliant shift matching to frontend dashboards.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.matching import ShiftMatchingEngine
from typing import Optional

router = APIRouter(
    prefix="/api/v1/shifts",
    tags=["Shift Scheduling & Automated Matching Engine"]
)


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/{shift_id}/matches",
    status_code=status.HTTP_200_OK,
    summary="Fetch ranked pool of OHCQ-cleared professionals matched to a shift gap"
)
async def get_shift_matches(
    shift_id: str,
    required_role: str = Query(..., description="License type required (RN, LPN, CNA, GNA)"),
    facility_id: str = Query(..., description="Facility requesting coverage"),
    require_background_check: bool = Query(True, description="Require background check clearance"),
    db: Session = Depends(get_db)
):
    """
    Exposes automated rank-order scheduling pools to the frontend dashboard, 
    guaranteeing only active, compliant candidates are selected.
    
    Query Parameters:
    - shift_id: Unique shift identifier
    - required_role: License type (RN, LPN, CNA, GNA)
    - facility_id: Target facility ID
    - require_background_check: Whether background check is required (default: True)
    
    Returns:
        Dictionary containing:
        - shift_id: The shift being filled
        - target_facility: Facility requesting coverage
        - required_role: License type required
        - total_eligible_matches_found: Count of qualified professionals
        - candidates: Ranked list of matched professionals with scores
        - compliance_summary: Overall workforce compliance stats
    
    Raises:
        HTTPException: If matching engine fails
    """
    try:
        engine = ShiftMatchingEngine(db)
        
        # Find compliant professionals
        matches = engine.find_compliant_professionals_for_shift(
            shift_id=shift_id,
            required_role=required_role,
            facility_id=facility_id,
            require_background_check=require_background_check
        )
        
        # Get compliance summary for context
        compliance_summary = engine.get_compliance_summary()
        
        return {
            "shift_id": shift_id,
            "target_facility": facility_id,
            "required_role": required_role,
            "total_eligible_matches_found": len(matches),
            "candidates": matches,
            "compliance_summary": compliance_summary,
            "matching_criteria": {
                "ohcq_verification_required": True,
                "background_check_required": require_background_check,
                "minimum_match_score": 50.0
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Automated matchmaking matrix calculation failed: {str(e)}"
        )


@router.get(
    "/available-by-role/{license_type}",
    status_code=status.HTTP_200_OK,
    summary="Get all available professionals for a specific license type"
)
async def get_available_by_role(
    license_type: str,
    fully_compliant_only: bool = Query(
        True,
        description="Require both OHCQ verification and background check"
    ),
    db: Session = Depends(get_db)
):
    """
    Returns all available professionals for a given license type.
    
    Useful for:
    - Building availability pools
    - Staff roster management
    - Capacity planning
    
    Args:
        license_type: RN, LPN, CNA, or GNA
        fully_compliant_only: Require full compliance (default: True)
    
    Returns:
        Dictionary with available professionals and summary stats
    """
    try:
        engine = ShiftMatchingEngine(db)
        
        professionals = engine.find_available_professionals_by_license_type(
            license_type=license_type,
            fully_compliant_only=fully_compliant_only
        )
        
        return {
            "license_type": license_type,
            "fully_compliant_only": fully_compliant_only,
            "total_available": len(professionals),
            "professionals": professionals
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve available professionals: {str(e)}"
        )


@router.get(
    "/compliance-summary",
    status_code=status.HTTP_200_OK,
    summary="Get workforce compliance summary statistics"
)
async def get_compliance_summary(db: Session = Depends(get_db)):
    """
    Returns overall workforce compliance statistics.
    
    Useful for:
    - Dashboard KPI widgets
    - Capacity planning
    - Compliance reporting
    
    Returns:
        Dictionary with compliance statistics
    """
    try:
        engine = ShiftMatchingEngine(db)
        summary = engine.get_compliance_summary()
        
        return {
            "compliance_summary": summary,
            "timestamp": __import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate compliance summary: {str(e)}"
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Matching engine health check"
)
async def matching_health():
    """Quick health check for matching service."""
    return {
        "status": "healthy",
        "service": "shift_matching_engine",
        "timestamp": __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc
        ).isoformat()
    }
