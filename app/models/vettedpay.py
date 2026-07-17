"""
VettedPay Database Models
Multi-rail payout tracking and compliance packet storage.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Numeric, Boolean, Text, Integer, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.database import Base


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
    rail = Column(String(50), nullable=False, unique=True)  # airwallex, nium, wise, etc.
    is_healthy = Column(Boolean, nullable=False, default=True)
    circuit_status = Column(String(20), nullable=False, default='CLOSED')  # CLOSED, OPEN, HALF_OPEN
    failure_count = Column(Integer, nullable=False, default=0)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    circuit_opened_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return (
            f"<VettedPayRailHealth(rail={self.rail}, healthy={self.is_healthy}, "
            f"circuit={self.circuit_status}, failures={self.failure_count})>"
        )
