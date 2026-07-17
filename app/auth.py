"""
VettedMe Authentication System

Production-grade JWT authentication with:
- Bcrypt password hashing
- Short-lived JWT tokens (1 hour)
- OAuth2 bearer token scheme
- Secure current_user dependency

Used by all protected endpoints.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.zktls import User

# ============================================================================
# Security Configuration
# ============================================================================

# JWT Secret Key - MUST be set in production via environment variable
SECRET_KEY = os.getenv(
    "JWT_SECRET", 
    "SUPERSECRET_VETTED_ME_DEV_KEY_DO_NOT_USE_IN_PROD"
)

# JWT Algorithm
ALGORITHM = "HS256"

# Token expiration (1 hour)
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 bearer token scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ============================================================================
# Password Hashing
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Bcrypt hashed password (safe to store in database)
        
    Example:
        >>> hash_password("mypassword123")
        '$2b$12$...'  # 60 character bcrypt hash
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a bcrypt hash.
    
    Args:
        plain_password: Plain text password from user
        hashed_password: Bcrypt hash from database
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT Token Management
# ============================================================================

def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Token payload (typically {"sub": email, "id": user_id})
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
        
    Example:
        >>> token = create_access_token({"sub": "user@example.com", "id": "uuid"})
        >>> # Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    to_encode = data.copy()
    
    # Calculate expiration
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add expiration to payload
    to_encode.update({"exp": expire})
    
    # Encode and sign JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload as dictionary
        
    Raises:
        JWTError: If token is invalid or expired
        
    Example:
        >>> payload = decode_access_token(token)
        >>> payload
        {"sub": "user@example.com", "id": "uuid", "exp": 1234567890}
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ============================================================================
# Current User Dependency
# ============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    This is a FastAPI dependency that:
    1. Extracts JWT token from Authorization header
    2. Decodes and verifies token
    3. Fetches user from database
    4. Returns User object
    
    Usage:
        @app.get("/profile")
        async def get_profile(current_user: User = Depends(get_current_user)):
            return {"email": current_user.email}
    
    Args:
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        User object from database
        
    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = decode_access_token(token)
        
        # Extract user info from token
        email: str = payload.get("sub")
        user_id: str = payload.get("id")
        
        if email is None or user_id is None:
            raise credentials_exception
        
    except JWTError:
        raise credentials_exception
    
    # Fetch user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and ensure they're active.
    
    This is a stricter version of get_current_user that
    explicitly checks the is_active flag.
    
    Usage:
        @app.post("/protected")
        async def protected_endpoint(user: User = Depends(get_current_active_user)):
            return {"user_id": user.id}
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and ensure email is verified.
    
    Use this for sensitive operations that require verified email.
    
    Usage:
        @app.post("/create-api-key")
        async def create_api_key(user: User = Depends(get_current_verified_user)):
            # Only verified users can create API keys
            pass
    """
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Check your inbox."
        )
    return current_user


# ============================================================================
# Optional Current User (for public endpoints)
# ============================================================================

async def get_current_user_optional(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    
    Use this for endpoints that work for both authenticated
    and anonymous users, but show different data.
    
    Usage:
        @app.get("/badges/{id}")
        async def get_badge(
            id: str,
            current_user: Optional[User] = Depends(get_current_user_optional)
        ):
            badge = get_badge(id)
            
            # Show private data only if user owns the badge
            if current_user and badge.user_id == current_user.id:
                return badge  # Full data
            else:
                return badge_public_only  # Public data only
    """
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


# ============================================================================
# Security Utilities
# ============================================================================

def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength.
    
    Requirements:
    - At least 8 characters
    - Contains uppercase letter
    - Contains lowercase letter
    - Contains number
    
    Args:
        password: Plain text password
        
    Returns:
        (is_valid, error_message)
        
    Example:
        >>> validate_password_strength("weak")
        (False, "Password must be at least 8 characters")
        
        >>> validate_password_strength("StrongPass123")
        (True, None)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    return True, None


# ============================================================================
# Legacy Support Functions (Old System Compatibility)
# ============================================================================

async def require_admin_api_key(api_key: str = Depends(oauth2_scheme)) -> bool:
    """
    Legacy admin API key validation.
    
    This is a compatibility function for the old deploy router.
    For new code, use get_current_user with role checking instead.
    """
    # For now, just check if it's a valid JWT token
    try:
        payload = decode_access_token(api_key)
        return True
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )


async def get_current_clinician(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Legacy clinician auth (compatibility stub).
    
    In the old system, this checked if user was a clinician.
    In the new system, we just return the current user.
    
    TODO: Add role-based access control when needed.
    """
    return current_user


async def get_current_caregiver(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Legacy caregiver auth (compatibility stub).
    
    In the old system, this checked if user was a caregiver.
    In the new system, we just return the current user.
    
    TODO: Add role-based access control when needed.
    """
    return current_user


async def get_current_facility_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Legacy facility user auth (compatibility stub).
    
    In the old system, this checked if user was a facility user.
    In the new system, we just return the current user.
    
    TODO: Add role-based access control when needed.
    """
    return current_user


async def require_manus_api_key(api_key: str = Depends(oauth2_scheme)) -> bool:
    """
    Legacy Manus API key validation (compatibility stub).
    
    This is for the old vettedcare router.
    For new code, use get_current_user instead.
    """
    try:
        payload = decode_access_token(api_key)
        return True
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )


async def get_current_clinician_optional(
    db: Session = Depends(get_db),
    token: Optional[str] = None
) -> Optional[User]:
    """
    Legacy optional clinician auth (compatibility stub).
    
    Returns None if not authenticated instead of raising an error.
    """
    if not token:
        return None
    
    try:
        # Manually decode token without requiring OAuth2 scheme
        payload = decode_access_token(token)
        user_id: str = payload.get("id")
        
        if not user_id:
            return None
        
        user = db.query(User).filter(User.id == user_id).first()
        return user if user and user.is_active else None
    except (JWTError, HTTPException):
        return None


# ============================================================================
# Token Blacklist (Future Enhancement)
# ============================================================================

# TODO: Implement token blacklist for logout
# - Store revoked tokens in Redis with expiration
# - Check blacklist in get_current_user
# - Clear blacklist when tokens expire naturally

# TODO: Implement refresh tokens
# - Issue long-lived refresh token (7 days)
# - Use refresh token to get new access token
# - Store refresh tokens in database
# - Implement token rotation on refresh
