"""
VettedPay Multi-Rail Payment Infrastructure

Provider-agnostic payment abstraction layer with:
- Compliance packet generation (ZK-proof + encrypted PII)
- Multiple financial rails (Airwallex, Nium, Wise, Stablecoin)
- Automatic failover and routing
- Transaction orchestration with ZK-proof verification
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

from .transaction_manager import VettedPayTransactionEngine

__all__ = [
    # Transaction Orchestration
    "VettedPayTransactionEngine",
    
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
