"""
VettedMe Python SDK
===================

The official Python library for the VettedMe Passport API.

Installation:
    pip install vettedme

Quick Start:
    import vettedme
    
    client = vettedme.Client(api_key="your_api_key")
    
    # Verify a credential
    result = client.verify("PASS-ABC-123")
    
    if result.valid:
        print(f"✅ Verified: {result.full_name}")
        print(f"Badges: {', '.join([b.type for b in result.badges])}")

Documentation:
    https://docs.vettedme.ai

"""

__version__ = "1.0.0"
__author__ = "VettedMe Team"
__license__ = "MIT"

from .client import Client
from .models import (
    Passport,
    Badge,
    VerificationResult,
    VerificationError,
    PassportCreate,
    BadgeCreate,
)
from .exceptions import (
    VettedMeError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

__all__ = [
    "Client",
    "Passport",
    "Badge",
    "VerificationResult",
    "VerificationError",
    "PassportCreate",
    "BadgeCreate",
    "VettedMeError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
]
