"""
Unified Matching Engine API Routes — Elite Systems Integration

Production-grade shift matching with complete enterprise component fusion:
- Component 1: CircuitBreaker (150ms registry checks)
- Component 2: SemanticMatcher (license-restricted vector matching)
- Component 3: BiasAuditor (tamper-evident hash-chained ledger)
- Component 4: VMSIngestPipeline (high-throughput shift data)

Zero legacy hardcoded algorithms. Full transaction safety. One unified pipeline.
"""

from __future__ import annotations

import logging
import uuid as uuid_module
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import CaregiverProfileResponse, ErrorResponse
from app.auth import get_current_clinician
from app.compliance import BiasAuditor, LedgerIntegrityError
from app.config import settings
from app.core.resilience import CircuitBreaker
from app.database import get_async_db
from app.models import MarylandProvider, OfferCareJobOffer, VMSShiftIngest
from app.services.matcher import MatchResult, SemanticMatcher
from app.services.mbon_verification import verify_mbon_license_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/matching", tags=["Matching"])


# ============================================================================
# SCHEMAS
# ============================================================================

class ShiftMatchRequest(BaseModel):
    """Request to match caregiver to shift."""
    shift_id: str = Field(description="Shift UUID to match")


class ShiftMatchResponse(BaseModel):
    """Response from shift matching."""
    match_id: str = Field(description="Unique match identifier")
    shift_id: str
    caregiver_id: str
    similarity_score: float = Field(ge=0.0, le=1.0, description="Semantic similarity (0-1)")
    compliance_passed: bool = Field(description="License boundary check")
    license_verified: bool = Field(description="MBON verification status")
    match_approved: bool = Field(description="Overall match approval")
    audit_record_id: str | None = Field(description="HB 1106 ledger entry ID")
    execution_time_ms: float = Field(description="Total processing time")


class AvailableShift(BaseModel):
    """Available shift for matching."""
    shift_id: str
    facility_id: str
    shift_start: datetime
    shift_end: datetime
    required_license: str
    hourly_rate: float
    crisis_rate: bool
    status: str
    similarity_score: float | None = None


class MatchedShiftsResponse(BaseModel):
    """List of matched shifts for caregiver."""
    total: int
    shifts: list[AvailableShift]
    caregiver: CaregiverProfileResponse


# ============================================================================
# UNIFIED MATCHING ENGINE INSTANCE
# ============================================================================

# Singleton instances (initialized on startup)
_circuit_breaker: CircuitBreaker | None = None
_semantic_matcher: SemanticMatcher | None = None
_bias_auditor: BiasAuditor | None = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create circuit breaker singleton."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout_seconds=30.0,
            latency_ceiling_ms=150.0,
            half_open_max_calls=1,
        )
    return _circuit_breaker


def get_semantic_matcher() -> SemanticMatcher:
    """Get or create semantic matcher singleton."""
    global _semantic_matcher
    if _semantic_matcher is None:
        _semantic_matcher = SemanticMatcher(vector_dimension=1536)
    return _semantic_matcher


def get_bias_auditor() -> BiasAuditor:
    """Get or create bias auditor singleton."""
    global _bias_auditor
    if _bias_auditor is None:
        _bias_auditor = BiasAuditor()
    return _bias_auditor


# ============================================================================
# ROUTE: GET MATCHED SHIFTS FOR CURRENT USER
# ============================================================================

@router.get(
    "/shifts",
    response_model=MatchedShiftsResponse,
    responses={
        200: {"description": "Matched shifts retrieved", "model": MatchedShiftsResponse},
        401: {"description": "Not authenticated", "model": ErrorResponse},
        500: {"description": "Internal error", "model": ErrorResponse},
    },
)
async def get_matched_shifts(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum shifts to return"),
    provider: MarylandProvider = Depends(get_current_clinician),
    db: AsyncSession = Depends(get_async_db),
    circuit_breaker: CircuitBreaker = Depends(get_circuit_breaker),
    semantic_matcher: SemanticMatcher = Depends(get_semantic_matcher),
) -> MatchedShiftsResponse:
    """
    Get matched shifts for current caregiver.
    
    Unified Pipeline:
    1. Verify license via MBON (CircuitBreaker protected, 150ms ceiling)
    2. Query available shifts from VMS ingest table
    3. Semantic match with license restrictions (SemanticMatcher)
    4. Return ranked list by similarity score
    
    Args:
        limit: Maximum number of shifts to return
        provider: Current authenticated caregiver
        db: Async database session
        circuit_breaker: Circuit breaker for MBON checks
        semantic_matcher: Semantic matcher for vector similarity
    
    Returns:
        MatchedShiftsResponse with ranked shifts
    """
    try:
        # Step 1: Verify license with circuit breaker (150ms ceiling)
        logger.info(f"Verifying license for provider {provider.provider_id}")
        try:
            license_result = await verify_mbon_license_async(
                provider=provider,
                db_session=db,
                circuit_breaker=circuit_breaker,
            )
            license_verified = license_result.status in ["ACTIVE", "PENDING_VERIFICATION"]
        except Exception as exc:
            logger.warning(f"License verification failed (fail-open): {exc}")
            license_verified = False
        
        # Step 2: Query available shifts from VMS ingest table
        logger.info(f"Querying available shifts for {provider.credential_type}")
        result = await db.execute(
            select(VMSShiftIngest)
            .where(VMSShiftIngest.status == "ACTIVE")
            .where(VMSShiftIngest.shift_start > datetime.now(timezone.utc))
            .order_by(VMSShiftIngest.shift_start)
            .limit(limit * 2)  # Over-fetch for filtering
        )
        vms_shifts = result.scalars().all()
        
        # Step 3: Semantic matching with license restrictions
        matched_shifts: list[AvailableShift] = []
        
        for shift in vms_shifts:
            try:
                # Invoke SemanticMatcher with license boundary enforcement
                match_results = await semantic_matcher.match_caregiver_to_shift(
                    caregiver_id=str(provider.provider_id),
                    facility_shift_id=str(shift.shift_id),
                    db_session=db,
                    dry_run=settings.SEMANTIC_MATCHER_DRY_RUN,
                )
                
                if not match_results or not match_results[0].compliance_passed:
                    # License boundary violation (e.g., CNA → LPN blocked)
                    logger.debug(
                        f"License boundary blocked: {provider.credential_type} → "
                        f"{shift.required_license}"
                    )
                    continue
                
                match_result = match_results[0]
                
                # Add to results
                matched_shifts.append(
                    AvailableShift(
                        shift_id=str(shift.shift_id),
                        facility_id=str(shift.facility_id),
                        shift_start=shift.shift_start,
                        shift_end=shift.shift_end,
                        required_license=shift.required_license,
                        hourly_rate=float(shift.hourly_rate),
                        crisis_rate=shift.crisis_rate,
                        status=shift.status,
                        similarity_score=match_result.similarity_score,
                    )
                )
                
                if len(matched_shifts) >= limit:
                    break
            
            except Exception as exc:
                logger.error(f"Matching error for shift {shift.shift_id}: {exc}", exc_info=True)
                continue
        
        # Sort by similarity score (descending)
        matched_shifts.sort(key=lambda s: s.similarity_score or 0.0, reverse=True)
        
        return MatchedShiftsResponse(
            total=len(matched_shifts),
            shifts=matched_shifts,
            caregiver=CaregiverProfileResponse.model_validate(provider),
        )
    
    except Exception as exc:
        logger.error(f"Get matched shifts error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "MATCHING_ERROR",
                "detail": "Failed to retrieve matched shifts. Please try again later.",
                "field": None,
            },
        ) from exc


# ============================================================================
# ROUTE: LOCK/CONFIRM SHIFT MATCH
# ============================================================================

@router.post(
    "/shifts/{shift_id}/lock",
    response_model=ShiftMatchResponse,
    responses={
        200: {"description": "Match locked successfully", "model": ShiftMatchResponse},
        400: {"description": "Invalid request", "model": ErrorResponse},
        401: {"description": "Not authenticated", "model": ErrorResponse},
        409: {"description": "Shift unavailable", "model": ErrorResponse},
        500: {"description": "Internal error", "model": ErrorResponse},
    },
)
async def lock_shift_match(
    shift_id: str,
    provider: MarylandProvider = Depends(get_current_clinician),
    db: AsyncSession = Depends(get_async_db),
    circuit_breaker: CircuitBreaker = Depends(get_circuit_breaker),
    semantic_matcher: SemanticMatcher = Depends(get_semantic_matcher),
    bias_auditor: BiasAuditor = Depends(get_bias_auditor),
) -> ShiftMatchResponse:
    """
    Lock shift match for caregiver with full enterprise pipeline.
    
    UNIFIED TRANSACTIONAL PIPELINE:
    1. Verify license (CircuitBreaker, 150ms ceiling)
    2. Semantic match validation (SemanticMatcher, license boundaries)
    3. Update shift status to LOCKED
    4. Create tamper-evident audit record (BiasAuditor, SHA-256 chain)
    5. Commit transaction OR rollback on any failure
    
    Args:
        shift_id: Shift UUID to lock
        provider: Current authenticated caregiver
        db: Async database session
        circuit_breaker: Circuit breaker for registry checks
        semantic_matcher: Semantic matcher for validation
        bias_auditor: Bias auditor for compliance logging
    
    Returns:
        ShiftMatchResponse with match details and audit ID
    
    Raises:
        HTTPException 409: Shift unavailable/already locked
        HTTPException 500: Pipeline failure with rollback
    """
    start_time = datetime.now()
    match_id = str(uuid_module.uuid4())
    
    try:
        logger.info(f"Match lock pipeline started: match_id={match_id}, shift={shift_id}")
        
        # ===== STEP 1: VERIFY LICENSE (CircuitBreaker Protected) =====
        logger.info(f"[{match_id}] Step 1: License verification (CircuitBreaker)")
        try:
            license_result = await verify_mbon_license_async(
                provider=provider,
                db_session=db,
                circuit_breaker=circuit_breaker,
            )
            
            license_verified = license_result.status in ["ACTIVE", "PENDING_VERIFICATION"]
            
            if not license_verified:
                logger.warning(
                    f"[{match_id}] License verification failed: status={license_result.status}"
                )
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "LICENSE_INVALID",
                        "detail": f"License status: {license_result.status}. Cannot lock shift.",
                        "field": "license",
                    },
                )
        
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"[{match_id}] License verification error (fail-open): {exc}")
            license_verified = False
        
        # ===== STEP 2: SEMANTIC MATCH VALIDATION (SemanticMatcher) =====
        logger.info(f"[{match_id}] Step 2: Semantic match validation (SemanticMatcher)")
        match_results = await semantic_matcher.match_caregiver_to_shift(
            caregiver_id=str(provider.provider_id),
            facility_shift_id=shift_id,
            db_session=db,
            dry_run=settings.SEMANTIC_MATCHER_DRY_RUN,
        )
        
        if not match_results or not match_results[0].compliance_passed:
            logger.warning(f"[{match_id}] License boundary violation")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "LICENSE_BOUNDARY_VIOLATION",
                    "detail": (
                        f"License mismatch: {provider.credential_type} cannot match "
                        f"{match_results[0].shift_license_required if match_results else 'shift'}"
                    ),
                    "field": "credential_type",
                },
            )
        
        match_result = match_results[0]
        
        # ===== STEP 3: UPDATE SHIFT STATUS TO LOCKED =====
        logger.info(f"[{match_id}] Step 3: Locking shift in database")
        
        # Check shift availability
        result = await db.execute(
            select(VMSShiftIngest).where(VMSShiftIngest.shift_id == shift_id)
        )
        shift = result.scalar_one_or_none()
        
        if shift is None:
            logger.warning(f"[{match_id}] Shift not found: {shift_id}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "SHIFT_NOT_FOUND",
                    "detail": "Shift not found or no longer available",
                    "field": "shift_id",
                },
            )
        
        if shift.status != "ACTIVE":
            logger.warning(f"[{match_id}] Shift unavailable: status={shift.status}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "SHIFT_UNAVAILABLE",
                    "detail": f"Shift is {shift.status}, cannot lock",
                    "field": "shift_id",
                },
            )
        
        # Update shift status
        shift.status = "LOCKED"
        shift.updated_at = datetime.now(timezone.utc)
        
        # ===== STEP 4: CREATE AUDIT RECORD (BiasAuditor) =====
        logger.info(f"[{match_id}] Step 4: Creating HB 1106 audit record (BiasAuditor)")
        
        audit_metadata = {
            "caregiver_license": provider.credential_type,
            "shift_license_required": shift.required_license,
            "region": str(shift.facility_id)[:8],
            "match_method": match_result.match_method,
            "compliance_passed": match_result.compliance_passed,
            "license_verified": license_verified,
            "circuit_breaker_state": str(circuit_breaker.state.value),
            "similarity_score": match_result.similarity_score,
            "hourly_rate": float(shift.hourly_rate),
            "crisis_rate": shift.crisis_rate,
        }
        
        audit_record = await bias_auditor.audit_and_chain_match(
            match_id=match_id,
            caregiver_id=str(provider.provider_id),
            facility_shift_id=shift_id,
            similarity_score=match_result.similarity_score,
            metadata=audit_metadata,
            db_session=db,
        )
        
        logger.info(
            f"[{match_id}] Audit record created: ledger_id={audit_record.ledger_id}, "
            f"block_hash={audit_record.block_hash[:16]}..."
        )
        
        # ===== STEP 5: COMMIT TRANSACTION =====
        logger.info(f"[{match_id}] Step 5: Committing transaction")
        await db.commit()
        await db.refresh(shift)
        
        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.info(
            f"[{match_id}] Match lock pipeline SUCCESS: "
            f"time={execution_time_ms:.2f}ms, "
            f"score={match_result.similarity_score:.2f}, "
            f"audit={audit_record.ledger_id}"
        )
        
        return ShiftMatchResponse(
            match_id=match_id,
            shift_id=shift_id,
            caregiver_id=str(provider.provider_id),
            similarity_score=match_result.similarity_score,
            compliance_passed=match_result.compliance_passed,
            license_verified=license_verified,
            match_approved=True,
            audit_record_id=audit_record.ledger_id,
            execution_time_ms=execution_time_ms,
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (already rolled back)
        raise
    
    except Exception as exc:
        # Unexpected error: rollback and return 500
        logger.critical(f"[{match_id}] Pipeline failure: {exc}", exc_info=True)
        await db.rollback()
        
        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "PIPELINE_FAILURE",
                "detail": "Match lock pipeline failed. Transaction rolled back. Please try again.",
                "field": None,
            },
        ) from exc


# ============================================================================
# ROUTE: VERIFY LEDGER INTEGRITY (Admin)
# ============================================================================

@router.get(
    "/admin/verify-ledger",
    response_model=dict[str, Any],
    responses={
        200: {"description": "Ledger integrity report"},
        500: {"description": "Ledger corruption detected", "model": ErrorResponse},
    },
)
async def verify_ledger_integrity(
    db: AsyncSession = Depends(get_async_db),
    bias_auditor: BiasAuditor = Depends(get_bias_auditor),
) -> dict[str, Any]:
    """
    Verify complete HB 1106 ledger integrity (admin endpoint).
    
    Scans entire bias audit ledger and recalculates SHA-256 hashes
    to detect any tampering or corruption.
    
    Returns:
        Verification report with status and statistics
    
    Raises:
        HTTPException 500: Ledger corruption detected
    """
    try:
        # BiasAuditor.verify_ledger_integrity raises LedgerIntegrityError on corruption
        report = await bias_auditor.verify_ledger_integrity(db)
        
        # If we get here, ledger is valid (no exception raised)
        logger.info(
            f"Ledger integrity verified: {report['verified_records']}/{report['total_records']} records"
        )
        return report
    
    except LedgerIntegrityError as exc:
        # Corruption detected — BiasAuditor already logged critical error
        logger.critical(f"LEDGER CORRUPTION DETECTED: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "LEDGER_CORRUPTED",
                "detail": str(exc),
                "field": None,
            },
        ) from exc
    
    except Exception as exc:
        logger.error(f"Ledger verification error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "VERIFICATION_ERROR",
                "detail": "Failed to verify ledger integrity. Please try again later.",
                "field": None,
            },
        ) from exc
