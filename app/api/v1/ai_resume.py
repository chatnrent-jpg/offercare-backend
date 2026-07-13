"""
VettedMe Enterprise Engine - AI Resume Parser API
FastAPI router for resume parsing with file upload support.
Includes audit trail logging and rate limiting.
"""

import hashlib
import json
import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.models import AIAuditLog
from app.schemas import (
    ParsedResumeResponse,
    AIAuditLogEntry,
)
from app.services.resume_parser import get_resume_parser, ResumeParserError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Resume Parser"])


@router.post(
    "/parse-resume",
    response_model=ParsedResumeResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_api_key)],
)
async def parse_resume_endpoint(
    resume_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    candidate_name: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Parse healthcare resume into structured data.
    
    **VettedMe Enterprise Engine AI Resume Parser**
    
    **Authentication Required:** Admin API Key via `X-Admin-Key` header
    
    Accepts either raw resume text or file upload (PDF/DOCX/TXT).
    Returns structured extraction with skills, certifications, work history, and education.
    
    **Input Options:**
    - `resume_text`: Raw text content of resume
    - `file`: Upload PDF, DOCX, or TXT file
    - `candidate_name`: Optional candidate name for context
    - `user_id`: Optional user identifier for audit trail
    
    **Returns:**
    - Structured resume data with verification metrics
    - AI audit trail reference
    - Confidence scores and verification flags
    
    **Error Handling:**
    - Graceful degradation if OpenAI unavailable
    - Returns partial results with keyword extraction
    - Comprehensive audit logging
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/ai/parse-resume \
      -H "X-Admin-Key: your-admin-key" \
      -F "file=@resume.pdf" \
      -F "candidate_name=John Doe"
    ```
    """
    # Validate input
    if not resume_text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either resume_text or file must be provided",
        )
    
    if resume_text and file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either resume_text or file, not both",
        )
    
    parser = get_resume_parser()
    input_text = ""
    filename = "text_input.txt"
    audit_id = str(uuid4())
    
    try:
        # Extract text from file if provided
        if file:
            filename = file.filename or "unknown.txt"
            file_content = await file.read()
            
            try:
                input_text = await parser.extract_text_from_file(file_content, filename)
            except ResumeParserError as e:
                logger.error("File extraction failed: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
        else:
            input_text = resume_text or ""
        
        # Validate extracted text
        if len(input_text.strip()) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume text too short - minimum 50 characters required",
            )
        
        # Generate input hash for audit trail
        input_hash = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        input_preview = input_text[:500] if len(input_text) > 500 else input_text
        
        # Parse resume
        parsed_data = await parser.parse_resume_text(input_text, candidate_name)
        
        # Extract AI metadata
        ai_metadata = parsed_data.pop("_ai_metadata", {})
        is_degraded = parsed_data.pop("_degraded", False)
        degradation_reason = parsed_data.pop("_reason", None)
        warning = parsed_data.pop("_warning", None)
        
        # Determine status
        audit_status = "SUCCESS"
        if is_degraded:
            audit_status = "DEGRADED"
        elif warning:
            audit_status = "SUCCESS_LOW_CONFIDENCE"
        
        # Create audit log
        try:
            audit_log = AIAuditLog(
                audit_id=audit_id,
                operation_type="resume_parse",
                model_used=ai_metadata.get("model", "degraded"),
                user_id=user_id,
                input_hash=input_hash,
                input_preview=input_preview,
                output_data=json.dumps(parsed_data, default=str),
                confidence_score=parsed_data.get("confidence_score"),
                tokens_used=ai_metadata.get("tokens"),
                cost_usd=ai_metadata.get("cost"),
                elapsed_ms=ai_metadata.get("elapsed_ms"),
                status=audit_status,
                error_message=degradation_reason,
            )
            db.add(audit_log)
            db.commit()
            logger.info("AI audit log created: %s", audit_id)
        except Exception as e:
            logger.error("Failed to create audit log: %s", e)
            db.rollback()
        
        # Build response
        response = ParsedResumeResponse(
            audit_id=audit_id,
            candidate_name=parsed_data.get("candidate_name", "Unknown"),
            email=parsed_data.get("email"),
            phone=parsed_data.get("phone"),
            skills=parsed_data.get("skills", []),
            certifications=parsed_data.get("certifications", []),
            work_history=parsed_data.get("work_history", []),
            education=parsed_data.get("education", []),
            confidence_score=parsed_data.get("confidence_score", 0.0),
            verification_flags=parsed_data.get("verification_flags", {}),
            tokens_used=ai_metadata.get("tokens"),
            cost_usd=ai_metadata.get("cost"),
            elapsed_ms=ai_metadata.get("elapsed_ms"),
            is_degraded=is_degraded,
            warning=warning or degradation_reason,
        )
        
        logger.info(
            "Resume parsed successfully: audit_id=%s confidence=%.2f",
            audit_id,
            response.confidence_score,
        )
        
        return response
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error("Resume parsing endpoint error: %s", e)
        
        # Log failure to audit trail
        try:
            audit_log = AIAuditLog(
                audit_id=audit_id,
                operation_type="resume_parse",
                model_used="error",
                user_id=user_id,
                input_hash=hashlib.sha256(input_text.encode("utf-8")).hexdigest() if input_text else "error",
                input_preview=input_text[:500] if input_text else "error",
                output_data=json.dumps({"error": str(e)}, default=str),
                status="FAILED",
                error_message=str(e),
            )
            db.add(audit_log)
            db.commit()
        except Exception as audit_error:
            logger.error("Failed to log error to audit trail: %s", audit_error)
            db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume parsing failed: {str(e)}",
        )


@router.post(
    "/extract-maryland-credentials",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_api_key)],
)
async def extract_maryland_credentials_endpoint(
    resume_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    candidate_name: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Extract Maryland nursing credentials from resume using AI.
    
    **VettedMe Intelligence Pillar - Phase 2**
    
    **Authentication Required:** Admin API Key via `X-Admin-Key` header
    
    Uses OpenAI Structured Output with Pydantic models to extract:
    - CNA, GNA, LPN, RN licenses
    - License numbers
    - Expiration dates
    
    **Returns:**
    - List of HealthcareCredentialSchema objects
    - Extraction metadata and confidence metrics
    - AI audit trail reference
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/ai/extract-maryland-credentials \
      -H "X-Admin-Key: your-admin-key" \
      -F "file=@resume.pdf" \
      -F "candidate_name=Jane Smith"
    ```
    """
    # Validate input
    if not resume_text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either resume_text or file must be provided",
        )
    
    parser = get_resume_parser()
    input_text = ""
    filename = "text_input.txt"
    audit_id = str(uuid4())
    
    try:
        # Extract text from file if provided
        if file:
            filename = file.filename or "unknown.txt"
            file_content = await file.read()
            
            try:
                input_text = await parser.extract_text_from_file(file_content, filename)
            except ResumeParserError as e:
                logger.error("File extraction failed: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
        else:
            input_text = resume_text or ""
        
        # Validate extracted text
        if len(input_text.strip()) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume text too short - minimum 50 characters required",
            )
        
        # Extract Maryland credentials
        extracted = await parser.extract_maryland_credentials(input_text, candidate_name)
        
        if not extracted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Credential extraction failed - AI service unavailable",
            )
        
        # Build audit log
        input_hash = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        
        # Extract AI metadata if available
        ai_metadata = getattr(extracted, "_ai_metadata", {})
        
        try:
            audit_log = AIAuditLog(
                audit_id=audit_id,
                operation_type="maryland_credential_extraction",
                model_used=ai_metadata.get("model", "gpt-4o-structured"),
                user_id=user_id,
                input_hash=input_hash,
                input_preview=input_text[:500],
                output_data=json.dumps({
                    "credentials": [c.model_dump() for c in extracted.credentials],
                    "extraction_notes": extracted.extraction_notes,
                    "found_count": extracted.found_count,
                }, default=str),
                confidence_score=1.0 if extracted.found_count > 0 else 0.0,
                tokens_used=ai_metadata.get("total_tokens"),
                cost_usd=ai_metadata.get("cost"),
                elapsed_ms=ai_metadata.get("elapsed_ms"),
                status="SUCCESS",
            )
            db.add(audit_log)
            db.commit()
            logger.info("Maryland credential extraction audit log created: %s", audit_id)
        except Exception as e:
            logger.error("Failed to create audit log: %s", e)
            db.rollback()
        
        # Return results
        return {
            "audit_id": audit_id,
            "candidate_name": candidate_name or "Unknown",
            "credentials": [c.model_dump() for c in extracted.credentials],
            "extraction_notes": extracted.extraction_notes,
            "found_count": extracted.found_count,
            "tokens_used": ai_metadata.get("total_tokens"),
            "cost_usd": ai_metadata.get("cost"),
            "elapsed_ms": ai_metadata.get("elapsed_ms"),
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error("Maryland credential extraction endpoint error: %s", e)
        
        # Log failure
        try:
            audit_log = AIAuditLog(
                audit_id=audit_id,
                operation_type="maryland_credential_extraction",
                model_used="error",
                user_id=user_id,
                input_hash=hashlib.sha256(input_text.encode("utf-8")).hexdigest() if input_text else "error",
                input_preview=input_text[:500] if input_text else "error",
                output_data=json.dumps({"error": str(e)}, default=str),
                status="FAILED",
                error_message=str(e),
            )
            db.add(audit_log)
            db.commit()
        except Exception as audit_error:
            logger.error("Failed to log error: %s", audit_error)
            db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Maryland credential extraction failed: {str(e)}",
        )


@router.get(
    "/audit/{audit_id}",
    response_model=AIAuditLogEntry,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_api_key)],
)
async def get_audit_log(
    audit_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve AI audit log entry by audit ID.
    
    **VettedMe Enterprise Engine AI Audit Trail**
    
    **Authentication Required:** Admin API Key via `X-Admin-Key` header
    
    Returns complete audit record for a specific AI operation.
    Enables compliance tracking and explainability.
    
    **Returns:**
    - Full audit log with input/output data
    - Performance metrics and cost tracking
    - Status and error information
    
    **Example:**
    ```bash
    curl -X GET http://localhost:8000/api/v1/ai/audit/{audit_id} \
      -H "X-Admin-Key: your-admin-key"
    ```
    """
    audit_log = db.query(AIAuditLog).filter(AIAuditLog.audit_id == audit_id).first()
    
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log not found: {audit_id}",
        )
    
    # Parse output data
    try:
        output_data = json.loads(audit_log.output_data)
    except json.JSONDecodeError:
        output_data = {"raw": audit_log.output_data}
    
    return AIAuditLogEntry(
        audit_id=audit_log.audit_id,
        operation_type=audit_log.operation_type,
        model_used=audit_log.model_used,
        user_id=audit_log.user_id,
        input_hash=audit_log.input_hash,
        input_preview=audit_log.input_preview,
        output_data=output_data,
        confidence_score=audit_log.confidence_score,
        tokens_used=audit_log.tokens_used,
        cost_usd=audit_log.cost_usd,
        elapsed_ms=audit_log.elapsed_ms,
        status=audit_log.status,
        error_message=audit_log.error_message,
        created_at=audit_log.created_at,
    )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_api_key)],
)
async def ai_health_check():
    """
    Check AI services health status.
    
    **VettedMe Enterprise Engine AI Health Check**
    
    **Authentication Required:** Admin API Key via `X-Admin-Key` header
    
    Returns status of OpenAI integration and resume parser.
    
    **Returns:**
    - AI service health status
    - Parser availability
    - Usage statistics
    
    **Example:**
    ```bash
    curl -X GET http://localhost:8000/api/v1/ai/health \
      -H "X-Admin-Key: your-admin-key"
    ```
    """
    parser = get_resume_parser()
    ai_client = parser.ai_client
    usage = ai_client.get_usage_summary()
    
    return {
        "status": "healthy" if parser.enabled else "degraded",
        "ai_enabled": ai_client.enabled,
        "parser_enabled": parser.enabled,
        "total_requests": usage["total_requests"],
        "total_cost_usd": usage["total_cost_usd"],
        "mode": "production" if parser.enabled else "graceful_degradation",
    }
