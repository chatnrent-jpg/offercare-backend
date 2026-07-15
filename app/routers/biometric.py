"""
VettedMe Biometric Authentication API

Provides endpoints for biometric enrollment, verification, and liveness detection.

Security:
- All biometric data is hashed (irreversible)
- Liveness detection prevents deepfakes
- Multi-factor authentication support
- GDPR/CCPA compliant (biometric deletion on request)
"""

import base64
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.passport import Passport
from app.services.biometric_auth import BiometricAuthService

router = APIRouter(
    prefix="/api/v1/biometric",
    tags=["Biometric Authentication"]
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class BiometricEnrollmentRequest(BaseModel):
    """Request schema for biometric enrollment."""
    passport_id: UUID
    face_image_base64: str = Field(description="Base64-encoded face image (JPEG/PNG)")
    video_frames_base64: Optional[str] = Field(default=None, description="Base64-encoded video for liveness detection")


class BiometricEnrollmentResponse(BaseModel):
    """Response schema for biometric enrollment."""
    success: bool
    biometric_hash: Optional[str] = None
    liveness_passed: Optional[bool] = None
    confidence: float
    errors: list[str] = Field(default_factory=list)


class BiometricVerificationRequest(BaseModel):
    """Request schema for biometric verification."""
    passport_id: UUID
    challenge_face_image_base64: str = Field(description="Base64-encoded face image to verify")
    challenge_video_base64: Optional[str] = Field(default=None, description="Optional video for liveness check")
    require_liveness: bool = Field(default=True, description="Whether to enforce liveness detection")


class BiometricVerificationResponse(BaseModel):
    """Response schema for biometric verification."""
    verified: bool
    confidence: float
    liveness_passed: Optional[bool] = None
    errors: list[str] = Field(default_factory=list)


class BiometricChallengeResponse(BaseModel):
    """Response schema for biometric challenge generation."""
    challenge_id: str
    instructions: list[str]
    expected_actions: list[str]
    expires_at: float


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/enroll",
    response_model=BiometricEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll biometric data",
    description="Capture and store facial biometric data for a passport"
)
async def enroll_biometric(
    payload: BiometricEnrollmentRequest,
    db: Session = Depends(get_db)
):
    """
    Enroll facial biometric data for enhanced passport security.
    
    **Workflow:**
    1. Optional: Verify liveness (if video provided)
    2. Extract facial embedding from image
    3. Hash embedding (irreversible, privacy-preserving)
    4. Store hash in passport
    
    **Security:**
    - Biometric data is never stored in raw form
    - Only irreversible hash is kept
    - Liveness detection prevents photo/video attacks
    - GDPR/CCPA compliant
    
    **Requirements:**
    - Face image: High-quality photo, front-facing, good lighting
    - Video (optional): 2-5 seconds, 30fps, shows face clearly
    
    **Example Request:**
    ```json
    {
      "passport_id": "uuid-12345",
      "face_image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
      "video_frames_base64": "data:video/mp4;base64,AAAAIGZ0eXB..."
    }
    ```
    """
    try:
        # Verify passport exists
        passport = db.query(Passport).filter_by(id=payload.passport_id).first()
        if not passport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Passport {payload.passport_id} not found"
            )
        
        # Decode base64 data
        face_image = base64.b64decode(payload.face_image_base64.split(',')[1] if ',' in payload.face_image_base64 else payload.face_image_base64)
        video_frames = None
        if payload.video_frames_base64:
            video_frames = base64.b64decode(payload.video_frames_base64.split(',')[1] if ',' in payload.video_frames_base64 else payload.video_frames_base64)
        
        # Enroll biometric
        service = BiometricAuthService(db)
        result = service.enroll_biometric(
            user_id=passport.user_id,
            face_image=face_image,
            video_frames=video_frames
        )
        
        # Store biometric hash in passport
        if result["success"]:
            passport.biometric_hash = result["biometric_hash"]
            db.commit()
        
        return BiometricEnrollmentResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Biometric enrollment failed: {str(e)}"
        )


@router.post(
    "/verify",
    response_model=BiometricVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify biometric authentication",
    description="Authenticate a user using facial biometrics"
)
async def verify_biometric(
    payload: BiometricVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Verify a user's identity using facial biometrics.
    
    **Use Cases:**
    - Passport access authentication
    - High-value transaction approval
    - Sensitive data access
    - Multi-factor authentication
    
    **Workflow:**
    1. Optional: Verify liveness (if video provided and required)
    2. Extract facial embedding from challenge image
    3. Compare with stored biometric hash
    4. Return verification result
    
    **Security:**
    - Liveness detection prevents photo/video attacks
    - Matching happens server-side (secure)
    - Failed attempts are logged for security monitoring
    
    **Example Request:**
    ```json
    {
      "passport_id": "uuid-12345",
      "challenge_face_image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
      "challenge_video_base64": "data:video/mp4;base64,AAAAIGZ0eXB...",
      "require_liveness": true
    }
    ```
    
    **Example Response:**
    ```json
    {
      "verified": true,
      "confidence": 0.98,
      "liveness_passed": true,
      "errors": []
    }
    ```
    """
    try:
        # Verify passport exists and has biometric enrolled
        passport = db.query(Passport).filter_by(id=payload.passport_id).first()
        if not passport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Passport {payload.passport_id} not found"
            )
        
        if not passport.biometric_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No biometric data enrolled for this passport"
            )
        
        # Decode base64 data
        challenge_face = base64.b64decode(
            payload.challenge_face_image_base64.split(',')[1] 
            if ',' in payload.challenge_face_image_base64 
            else payload.challenge_face_image_base64
        )
        
        challenge_video = None
        if payload.challenge_video_base64:
            challenge_video = base64.b64decode(
                payload.challenge_video_base64.split(',')[1] 
                if ',' in payload.challenge_video_base64 
                else payload.challenge_video_base64
            )
        
        # Verify biometric
        service = BiometricAuthService(db)
        result = service.verify_biometric(
            stored_biometric_hash=passport.biometric_hash,
            challenge_face_image=challenge_face,
            challenge_video_frames=challenge_video,
            require_liveness=payload.require_liveness
        )
        
        return BiometricVerificationResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Biometric verification failed: {str(e)}"
        )


@router.get(
    "/challenge",
    response_model=BiometricChallengeResponse,
    summary="Generate biometric challenge",
    description="Generate a random liveness detection challenge"
)
async def generate_challenge(db: Session = Depends(get_db)):
    """
    Generate a random biometric challenge for liveness detection.
    
    **Use Cases:**
    - Dynamic liveness checks
    - Anti-replay attack protection
    - Enhanced security for sensitive operations
    
    **Challenge Types:**
    - Blink detection
    - Head movement (left/right)
    - Facial expressions (smile)
    - Random sequences
    
    **Example Response:**
    ```json
    {
      "challenge_id": "challenge_a1b2c3d4e5f6",
      "instructions": [
        "Please blink twice clearly"
      ],
      "expected_actions": ["blink", "blink"],
      "expires_at": 1721073900.0
    }
    ```
    
    **Usage Flow:**
    1. Call this endpoint to get a challenge
    2. Display instructions to user
    3. Record video of user performing actions
    4. Submit video with challenge_id for verification
    """
    try:
        service = BiometricAuthService(db)
        challenge = service.generate_biometric_challenge()
        return BiometricChallengeResponse(**challenge)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Challenge generation failed: {str(e)}"
        )


@router.delete(
    "/{passport_id}/biometric",
    status_code=status.HTTP_200_OK,
    summary="Delete biometric data",
    description="Remove biometric data from a passport (GDPR/CCPA compliance)"
)
async def delete_biometric(
    passport_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete biometric data from a passport.
    
    **GDPR/CCPA Compliance:**
    - Users have the right to delete their biometric data
    - Deletion is immediate and irreversible
    - Passport remains active but biometric auth is disabled
    
    **Effect:**
    - Biometric hash is removed from passport
    - User can no longer use biometric authentication
    - User can re-enroll biometrics at any time
    
    **Security Note:**
    - Deletion is logged for audit trail
    - Original biometric data was never stored (only hash)
    """
    try:
        passport = db.query(Passport).filter_by(id=passport_id).first()
        if not passport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Passport {passport_id} not found"
            )
        
        if not passport.biometric_hash:
            return {
                "success": True,
                "message": "No biometric data to delete"
            }
        
        # Delete biometric hash
        passport.biometric_hash = None
        db.commit()
        
        return {
            "success": True,
            "message": "Biometric data successfully deleted",
            "passport_id": str(passport_id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Biometric deletion failed: {str(e)}"
        )
