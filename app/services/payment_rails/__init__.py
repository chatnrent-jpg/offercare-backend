"""
VettedPay Multi-Rail Payment Infrastructure

Provider-agnostic payment abstraction layer with:
- Compliance packet generation (ZK-proof + encrypted PII)
- Multiple financial rails (Airwallex, Nium, Wise, Stablecoin)
- Automatic failover and routing
- Zero platform lock-in
"""

from .payout_adapter import (
    PayoutProviderAdapter,
    PayoutRail,
    PayoutStatus,
    PayoutResult,
    PayoutProviderError,
    ComplianceVerificationError,
    InsufficientFundsError,
    InvalidDestinationError,
    RateLimitError,
)

from .compliance_packet import (
    CompliancePacketGenerator,
    CompliancePacket,
    CompliancePayload,
    ZKProof,
    CompliancePacketError,
    InvalidPacketSignatureError,
    EncryptionError,
    MissingPublicKeyError,
)

__all__ = [
    # Adapter Pattern
    "PayoutProviderAdapter",
    "PayoutRail",
    "PayoutStatus",
    "PayoutResult",
    
    # Compliance Layer
    "CompliancePacketGenerator",
    "CompliancePacket",
    "CompliancePayload",
    "ZKProof",
    
    # Exceptions
    "PayoutProviderError",
    "ComplianceVerificationError",
    "InsufficientFundsError",
    "InvalidDestinationError",
    "RateLimitError",
    "CompliancePacketError",
    "InvalidPacketSignatureError",
    "EncryptionError",
    "MissingPublicKeyError",
]
