"""
VettedMe Authentication API

Endpoints for user registration, login, and profile management.

Phase 1: Email/password authentication
Phase 2: OAuth (Google, GitHub, LinkedIn)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import timedelta
import logging

from app.database import get_db
from app.models.zktls import User, PublicProfile
from app.schemas.zktls import UserResponse, UserProfile
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_active_user,
    validate_password_strength,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


# ============================================================================
# Request/Response Models
# ============================================================================

class UserRegister(BaseModel):
    """User registration request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, description="Full name")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username for public profile")
    
    @validator('username')
    def validate_username(cls, v):
        if v:
            # Username must be alphanumeric + underscores
            if not v.replace('_', '').isalnum():
                raise ValueError('Username must contain only letters, numbers, and underscores')
            
            # Cannot start with underscore
            if v.startswith('_'):
                raise ValueError('Username cannot start with underscore')
            
            # Reserved usernames
            reserved = ['admin', 'api', 'www', 'app', 'support', 'help', 'vettedme']
            if v.lower() in reserved:
                raise ValueError('Username is reserved')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "password": "SecurePass123",
                "full_name": "John Doe",
                "username": "johndoe"
            }
        }


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenWithUser(Token):
    """Token response with user info"""
    user: UserResponse


# ============================================================================
# Registration
# ============================================================================

@router.post(
    "/register",
    response_model=TokenWithUser,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
    description="""
    Register a new user account.
    
    **Requirements:**
    - Unique email address
    - Password: min 8 chars, uppercase, lowercase, number
    - Optional: Full name and username
    
    **Username Rules:**
    - 3-50 characters
    - Alphanumeric + underscores only
    - Cannot start with underscore
    - Cannot be reserved (admin, api, etc.)
    
    **Response:**
    - JWT token (valid for 1 hour)
    - User profile data
    
    **Public Profile:**
    - Automatically created at: vettedme.ai/@{username}
    - Initially empty (no badges yet)
    """
)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Creates:
    1. User record
    2. Public profile (if username provided)
    3. JWT token for immediate login
    """
    # ========================================================================
    # Step 1: Validate Email Not Already Registered
    # ========================================================================
    
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # ========================================================================
    # Step 2: Validate Username Not Taken (if provided)
    # ========================================================================
    
    if user_data.username:
        existing_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # ========================================================================
    # Step 3: Validate Password Strength
    # ========================================================================
    
    is_valid, error_message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # ========================================================================
    # Step 4: Create User
    # ========================================================================
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        username=user_data.username
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Created user: {user.email} (ID: {user.id})")
    
    # ========================================================================
    # Step 5: Create Public Profile
    # ========================================================================
    
    public_profile = PublicProfile(
        user_id=user.id,
        display_name=user_data.full_name or user_data.email.split('@')[0],
        is_public=True
    )
    
    db.add(public_profile)
    db.commit()
    
    logger.info(f"Created public profile for user: {user.id}")
    
    # ========================================================================
    # Step 6: Generate JWT Token
    # ========================================================================
    
    access_token = create_access_token(
        data={"sub": user.email, "id": str(user.id)}
    )
    
    # ========================================================================
    # Step 7: Return Token + User Data
    # ========================================================================
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        "user": UserResponse.from_orm(user)
    }


# ============================================================================
# Login
# ============================================================================

@router.post(
    "/login",
    response_model=TokenWithUser,
    summary="User Login",
    description="""
    Authenticate user and receive JWT token.
    
    **Method 1: JSON Body**
    ```json
    {
        "email": "user@example.com",
        "password": "password123"
    }
    ```
    
    **Method 2: OAuth2 Form (for Swagger UI)**
    - username: email address
    - password: password
    
    **Response:**
    - JWT token (valid for 1 hour)
    - User profile data
    
    **Usage:**
    Include token in subsequent requests:
    ```
    Authorization: Bearer <token>
    ```
    """
)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with email/password.
    
    Returns JWT token for API access.
    """
    # ========================================================================
    # Step 1: Find User by Email
    # ========================================================================
    
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user:
        # Don't reveal whether email exists (security best practice)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ========================================================================
    # Step 2: Verify Password
    # ========================================================================
    
    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ========================================================================
    # Step 3: Check if User is Active
    # ========================================================================
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact support."
        )
    
    # ========================================================================
    # Step 4: Generate JWT Token
    # ========================================================================
    
    access_token = create_access_token(
        data={"sub": user.email, "id": str(user.id)}
    )
    
    logger.info(f"User logged in: {user.email}")
    
    # ========================================================================
    # Step 5: Return Token + User Data
    # ========================================================================
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserResponse.from_orm(user)
    }


@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 Token Endpoint (Swagger UI)",
    description="OAuth2-compatible token endpoint for Swagger UI authentication"
)
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2-compatible token endpoint.
    
    This endpoint is specifically for Swagger UI's "Authorize" button.
    It expects form data instead of JSON.
    """
    # Treat username field as email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "id": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


# ============================================================================
# Profile Management
# ============================================================================

@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get Current User Profile",
    description="""
    Get the profile of the currently authenticated user.
    
    **Requires Authentication:**
    ```
    Authorization: Bearer <token>
    ```
    
    **Returns:**
    - User profile data
    - Credential count
    - Public profile URL
    """
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile"""
    
    # Count user's credentials
    from app.models.zktls import Credential
    credential_count = db.query(Credential).filter(
        Credential.user_id == current_user.id
    ).count()
    
    # Build public profile URL
    public_profile_url = None
    if current_user.username:
        public_profile_url = f"https://vettedme.ai/@{current_user.username}"
    
    return {
        **UserResponse.from_orm(current_user).dict(),
        "credential_count": credential_count,
        "public_profile_url": public_profile_url
    }


@router.post(
    "/logout",
    summary="User Logout",
    description="""
    Logout current user.
    
    **Note:** JWT tokens are stateless, so logout is client-side only.
    Client should delete the token from storage.
    
    Future enhancement: Implement token blacklist for server-side logout.
    """
)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user.
    
    Currently this is a no-op since JWTs are stateless.
    Client should delete token from localStorage/cookies.
    
    TODO: Implement token blacklist in Redis
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return {
        "success": True,
        "message": "Logged out successfully. Delete token from client storage."
    }


# ============================================================================
# Password Management (Future)
# ============================================================================

# TODO: Implement these endpoints

# @router.post("/forgot-password")
# async def forgot_password(email: EmailStr):
#     """Send password reset email"""
#     pass

# @router.post("/reset-password")
# async def reset_password(token: str, new_password: str):
#     """Reset password with token from email"""
#     pass

# @router.post("/change-password")
# async def change_password(
#     old_password: str,
#     new_password: str,
#     current_user: User = Depends(get_current_user)
# ):
#     """Change password (requires old password)"""
#     pass


# ============================================================================
# Email Verification (Future)
# ============================================================================

# TODO: Implement these endpoints

# @router.post("/send-verification-email")
# async def send_verification_email(current_user: User = Depends(get_current_user)):
#     """Send email verification link"""
#     pass

# @router.post("/verify-email")
# async def verify_email(token: str):
#     """Verify email with token from email"""
#     pass
