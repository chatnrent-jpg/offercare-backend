"""
VettedMe Enterprise Engine - AI Audit Trail Model
SQLAlchemy model for logging all AI decisions and operations.
Enables explainability, compliance auditing, and cost tracking.
"""

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, func, Index
from uuid import uuid4

from app.database import Base


class AIAuditLog(Base):
    """
    AI audit trail persistence layer for VettedMe Enterprise Engine.
    Tracks all AI operations for compliance, explainability, and cost analysis.
    """
    __tablename__ = "ai_audit_logs"
    
    # Primary key
    audit_id = Column(String(50), primary_key=True, index=True, nullable=False, default=lambda: str(uuid4()))
    
    # Operation metadata
    operation_type = Column(String(100), nullable=False, index=True)
    model_used = Column(String(50), nullable=False)
    user_id = Column(String(50), nullable=True, index=True)
    
    # Input/Output tracking
    input_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash
    input_preview = Column(Text, nullable=True)  # First 500 chars for debugging
    output_data = Column(Text, nullable=False)  # Full output (JSON or text)
    
    # Quality metrics
    confidence_score = Column(Float, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    elapsed_ms = Column(Integer, nullable=True)
    
    # Status and flags
    status = Column(String(30), nullable=False, default="SUCCESS")  # SUCCESS, FAILED, DEGRADED
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_ai_audit_operation_created", "operation_type", "created_at"),
        Index("idx_ai_audit_user_created", "user_id", "created_at"),
        Index("idx_ai_audit_status_created", "status", "created_at"),
    )
    
    def __repr__(self):
        return (
            f"<AIAuditLog(audit_id={self.audit_id}, "
            f"operation={self.operation_type}, "
            f"model={self.model_used}, "
            f"status={self.status})>"
        )
