"""VettedMe Data Models"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class BadgeType(str, Enum):
    """Badge types supported by VettedMe"""
    HEALTHCARE = "HEALTHCARE"
    SECURITY_CLEARANCE = "SECURITY_CLEARANCE"
    INSURANCE = "INSURANCE"
    FINANCIAL_ADVISOR = "FINANCIAL_ADVISOR"
    REAL_ESTATE = "REAL_ESTATE"
    LAWYER = "LAWYER"
    EDUCATION = "EDUCATION"
    EMPLOYMENT = "EMPLOYMENT"
    BIOMETRIC_ID = "BIOMETRIC_ID"
    CRIMINAL_BACKGROUND = "CRIMINAL_BACKGROUND"
    CREDIT_HISTORY = "CREDIT_HISTORY"
    PROFESSIONAL_LICENSE = "PROFESSIONAL_LICENSE"


class BadgeStatus(str, Enum):
    """Badge verification status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"


class Passport:
    """VettedMe Passport"""
    
    def __init__(self, **data):
        self.id: str = data.get("id")
        self.user_id: str = data.get("user_id")
        self.full_name: str = data.get("full_name")
        self.email: str = data.get("email")
        self.phone: Optional[str] = data.get("phone")
        self.passport_number: str = data.get("passport_number")
        self.trust_score: int = data.get("trust_score", 0)
        self.status: str = data.get("status", "active")
        self.issuer_signature: str = data.get("issuer_signature")
        self.issued_at: datetime = self._parse_datetime(data.get("issued_at"))
        self.expires_at: Optional[datetime] = self._parse_datetime(data.get("expires_at"))
        self.badges: List[Badge] = [Badge(**b) for b in data.get("badges", [])]
        self.verification_count: int = data.get("verification_count", 0)
        self.last_verified_at: Optional[datetime] = self._parse_datetime(data.get("last_verified_at"))
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    def __repr__(self):
        return f"<Passport {self.passport_number} - {self.full_name}>"


class Badge:
    """Credential Badge"""
    
    def __init__(self, **data):
        self.id: str = data.get("id")
        self.passport_id: str = data.get("passport_id")
        self.type: str = data.get("type")
        self.credential_data: Dict[str, Any] = data.get("credential_data", {})
        self.status: str = data.get("status", "active")
        self.issuer_signature: str = data.get("issuer_signature")
        self.issued_at: datetime = self._parse_datetime(data.get("issued_at"))
        self.expires_at: Optional[datetime] = self._parse_datetime(data.get("expires_at"))
        self.verification_count: int = data.get("verification_count", 0)
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    @property
    def is_expired(self) -> bool:
        """Check if badge is expired"""
        if self.expires_at is None:
            return False
        return datetime.now(self.expires_at.tzinfo) > self.expires_at
    
    def __repr__(self):
        return f"<Badge {self.type} - {self.status}>"


class VerificationResult:
    """Result of a verification request"""
    
    def __init__(self, **data):
        self.valid: bool = data.get("valid", False)
        self.passport_id: str = data.get("passport_id")
        self.full_name: str = data.get("full_name")
        self.trust_score: int = data.get("trust_score", 0)
        self.badges: List[Badge] = [Badge(**b) for b in data.get("badges", [])]
        self.verified_at: datetime = self._parse_datetime(data.get("verified_at"))
        self.signature_valid: bool = data.get("signature_valid", False)
        self.warnings: List[str] = data.get("warnings", [])
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    def __repr__(self):
        status = "✅ VALID" if self.valid else "❌ INVALID"
        return f"<VerificationResult {status} - {self.full_name}>"
    
    def __bool__(self):
        """Allow: if verification_result: ..."""
        return self.valid


class VerificationError:
    """Verification error details"""
    
    def __init__(self, **data):
        self.code: str = data.get("code")
        self.message: str = data.get("message")
        self.details: Dict[str, Any] = data.get("details", {})


class PassportCreate:
    """Data for creating a new passport"""
    
    def __init__(
        self,
        full_name: str,
        email: str,
        phone: Optional[str] = None,
        **extra
    ):
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self.extra = extra
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            **self.extra
        }


class BadgeCreate:
    """Data for creating a new badge"""
    
    def __init__(
        self,
        type: str,
        credential_data: Dict[str, Any],
        expires_at: Optional[datetime] = None,
        **extra
    ):
        self.type = type
        self.credential_data = credential_data
        self.expires_at = expires_at
        self.extra = extra
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "type": self.type,
            "credential_data": self.credential_data,
            **self.extra
        }
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        return data


class WebhookSubscription:
    """Webhook subscription"""
    
    def __init__(self, **data):
        self.id: str = data.get("id")
        self.url: str = data.get("url")
        self.events: List[str] = data.get("events", [])
        self.secret: Optional[str] = data.get("secret")
        self.active: bool = data.get("active", True)
        self.created_at: datetime = self._parse_datetime(data.get("created_at"))
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    def __repr__(self):
        return f"<WebhookSubscription {self.url}>"


class APIKey:
    """API key"""
    
    def __init__(self, **data):
        self.id: str = data.get("id")
        self.name: str = data.get("name")
        self.key: Optional[str] = data.get("key")  # Only returned on creation
        self.permissions: List[str] = data.get("permissions", [])
        self.active: bool = data.get("active", True)
        self.created_at: datetime = self._parse_datetime(data.get("created_at"))
        self.last_used_at: Optional[datetime] = self._parse_datetime(data.get("last_used_at"))
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    def __repr__(self):
        return f"<APIKey {self.name}>"
