"""
VettedPay Database Models
Privacy-compliant transaction tracking and multi-rail orchestration.
Never stores raw bank accounts, SSNs, or unencrypted PII.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Numeric, Boolean, Text, Integer, Index, Enum as SQLEnum, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class PaymentRail(enum.Enum):
    """Available payment rails"""
    AIRWALLEX = "airwallex"
    NIUM = "nium"
    WISE = "wise"
    STABLECOIN_USDC = "stablecoin_usdc"
    FALLBACK_MOCK = "fallback_mock"


class TransactionStatus(enum.Enum):
    """Transaction lifecycle states"""
    INITIATED = "initiated"
    ZK_VERIFIED = "zk_verified"
    DISPATCHED_TO_RAIL = "dispatched_to_rail"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VettedPayPayout(Base):
    """
    VettedPay payout transaction record.
    Tracks payouts across all financial rails (Airwallex, Nium, Wise, etc.)
    """
    __tablename__ = "vettedpay_payouts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    provider_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    destination = Column(String(255), nullable=False)
    rail = Column(String(50), nullable=False, index=True)  # airwallex, nium, wise, stablecoin
    status = Column(String(50), nullable=False, index=True)  # pending, processing, completed, failed, cancelled
    transaction_id = Column(String(255), nullable=True, index=True)
    provider_reference = Column(String(255), nullable=True)  # Provider's internal transaction ID
    compliance_packet_id = Column(String(255), nullable=False)
    compliance_verified = Column(Boolean, nullable=False, default=False)
    fees = Column(Numeric(10, 2), nullable=True)
    estimated_arrival = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)  # Additional payout details
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_payouts_provider_status', 'provider_id', 'status'),
        Index('ix_payouts_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return (
            f"<VettedPayPayout(id={self.id}, provider={self.provider_id}, "
            f"amount={self.amount} {self.currency}, rail={self.rail}, status={self.status})>"
        )


class VettedPayCompliancePacket(Base):
    """
    Compliance packet storage.
    Contains ZK-proof and encrypted PII payload.
    Server never has access to decrypted PII.
    """
    __tablename__ = "vettedpay_compliance_packets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    packet_id = Column(String(255), nullable=False, unique=True, index=True)
    provider_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    zk_proof_hash = Column(String(64), nullable=False)  # Hash of sanction check
    zk_proof_signature = Column(String(64), nullable=False)  # Cryptographic signature
    encrypted_payload = Column(Text, nullable=False)  # Base64 encoded encrypted PII
    encryption_algorithm = Column(String(50), nullable=False)
    recipient_key_fingerprint = Column(String(16), nullable=False)
    packet_signature = Column(String(64), nullable=False)  # HMAC of entire packet
    recipient_bank_id = Column(String(50), nullable=False)
    sanction_check_result = Column(String(20), nullable=False, index=True)  # CLEAR, FLAGGED, PENDING
    verification_method = Column(String(50), nullable=False)  # OFAC_API_v1, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_compliance_provider_created', 'provider_id', 'created_at'),
    )
    
    def __repr__(self):
        return (
            f"<VettedPayCompliancePacket(packet_id={self.packet_id}, "
            f"provider={self.provider_id}, result={self.sanction_check_result})>"
        )


class VettedPayRailHealth(Base):
    """
    Payment rail health status and circuit breaker state.
    Tracks availability and failure counts for each rail.
    """
    __tablename__ = "vettedpay_rail_health"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rail = Column(SQLEnum(PaymentRail, name='payment_rail'), nullable=False, unique=True)
    is_healthy = Column(Boolean, nullable=False, default=True)
    circuit_status = Column(String(20), nullable=False, default='CLOSED')  # CLOSED, OPEN, HALF_OPEN
    failure_count = Column(Integer, nullable=False, default=0)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return (
            f"<VettedPayRailHealth(rail={self.rail.value if self.rail else None}, healthy={self.is_healthy}, "
            f"circuit={self.circuit_status}, failures={self.failure_count})>"
        )


class VettedPayTransaction(Base):
    """
    Core transaction ledger - privacy-compliant.
    Never stores raw bank accounts, SSNs, or unencrypted PII.
    Uses decentralized identifiers (DIDs) instead of real names.
    """
    __tablename__ = "vettedpay_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)
    sender_did = Column(String(255), nullable=False, index=True)  # Decentralized identifier
    recipient_did = Column(String(255), nullable=False, index=True)
    amount = Column(Numeric(14, 4), nullable=False)
    currency = Column(String(3), nullable=False, server_default='USD')
    active_rail = Column(SQLEnum(PaymentRail, name='payment_rail'), nullable=False, index=True)
    status = Column(SQLEnum(TransactionStatus, name='transaction_status'), nullable=False, server_default='initiated', index=True)
    rail_transaction_id = Column(String(255), nullable=True)
    zk_proof_verified = Column(Boolean, nullable=False, server_default='false')
    compliance_packet_id = Column(String(255), nullable=True)
    error_log = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_transactions_sender', 'sender_did'),
        Index('idx_transactions_recipient', 'recipient_did'),
        Index('idx_transactions_status', 'status'),
        Index('idx_transactions_rail', 'active_rail'),
    )
    
    def __repr__(self):
        return (
            f"<VettedPayTransaction(id={self.id}, sender={self.sender_did}, "
            f"amount={self.amount} {self.currency}, rail={self.active_rail.value if self.active_rail else None}, "
            f"status={self.status.value if self.status else None})>"
        )


class VettedPayZKVerification(Base):
    """
    Audit trail of zero-knowledge proof verifications.
    Does NOT store actual proofs (too large), only verification results.
    """
    __tablename__ = "vettedpay_zk_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey('vettedpay_transactions.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_did = Column(String(255), nullable=False, index=True)
    proof_type = Column(String(50), nullable=False)
    verification_result = Column(Boolean, nullable=False)
    verification_method = Column(String(100), nullable=False)
    proof_timestamp = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return (
            f"<VettedPayZKVerification(transaction={self.transaction_id}, "
            f"sender={self.sender_did}, result={self.verification_result})>"
        )


class VettedPayWaitlist(Base):
    """
    Early adopter waitlist for VettedPay launch.
    Captures interest before full public availability.
    """
    __tablename__ = "vettedpay_waitlist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    use_case = Column(Text, nullable=True)
    referral_source = Column(String(100), nullable=True)
    priority_score = Column(Integer, nullable=False, server_default='0')
    status = Column(String(50), nullable=False, server_default='pending', index=True)
    invited_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_waitlist_priority', 'priority_score', postgresql_ops={'priority_score': 'DESC'}),
    )
    
    def __repr__(self):
        return (
            f"<VettedPayWaitlist(email={self.email}, status={self.status}, "
            f"priority={self.priority_score})>"
        )
