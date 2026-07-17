"""
VettedPay API Router
Privacy-first payment transfer endpoints with zero-knowledge compliance.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import logging

from app.database import get_db
from app.models.vettedpay import (
    VettedPayTransaction,
    VettedPayZKVerification,
    VettedPayRailHealth,
    VettedPayWaitlist,
    PaymentRail,
    TransactionStatus,
)
from app.services.payment_rails import VettedPayTransactionEngine
from app.services.payment_rails.compliance_packet import CompliancePacketGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vettedpay", tags=["VettedPay"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class ZKProofSchema(BaseModel):
    """Zero-knowledge proof of non-sanction status"""
    valid: bool
    timestamp: str
    verification_method: str = "OFAC_API_v1"
    provider_hash: Optional[str] = None
    signature: Optional[str] = None
    nonce: Optional[str] = None


class TransferRequestSchema(BaseModel):
    """Transfer initiation request from frontend"""
    sender_did: str = Field(..., min_length=10, max_length=255, description="Sender's DID")
    recipient_did: str = Field(..., min_length=10, max_length=255, description="Recipient's DID")
    amount: float = Field(..., gt=0, description="Transfer amount")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO currency code")
    zk_proof: ZKProofSchema
    encrypted_compliance_packet: str = Field(..., min_length=100, description="RSA-encrypted bank details")
    destination_account: str = Field(..., description="Encrypted account reference")
    metadata: Optional[Dict[str, Any]] = None

    @validator('currency')
    def validate_currency(cls, v):
        valid_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF']
        if v.upper() not in valid_currencies:
            raise ValueError(f"Invalid currency. Must be one of: {', '.join(valid_currencies)}")
        return v.upper()

    @validator('sender_did', 'recipient_did')
    def validate_did(cls, v):
        if not v.startswith('did:'):
            raise ValueError("Invalid DID format. Must start with 'did:'")
        return v


class TransferResponseSchema(BaseModel):
    """Transfer initiation response"""
    success: bool
    transaction_id: str
    idempotency_key: str
    status: str
    rail: str
    amount: float
    currency: str
    compliance_verified: bool
    created_at: str
    message: Optional[str] = None
    error: Optional[str] = None


class TransactionDetailSchema(BaseModel):
    """Detailed transaction information"""
    id: str
    sender_did: str
    recipient_did: str
    amount: str
    currency: str
    status: str
    rail: str
    zk_proof_verified: bool
    rail_transaction_id: Optional[str]
    error_log: Optional[str]
    created_at: str
    updated_at: str


class RailHealthSchema(BaseModel):
    """Payment rail health status"""
    rail: str
    is_healthy: bool
    circuit_status: str
    failure_count: int
    last_success_at: Optional[str]
    last_failure_at: Optional[str]
    error_message: Optional[str]


class WaitlistSignupSchema(BaseModel):
    """Waitlist signup request"""
    email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    full_name: Optional[str] = Field(None, max_length=255)
    organization: Optional[str] = Field(None, max_length=255)
    use_case: Optional[str] = None
    referral_source: Optional[str] = Field(None, max_length=100)


# ============================================================================
# Transfer Endpoints
# ============================================================================

@router.post("/transfer", response_model=TransferResponseSchema, status_code=status.HTTP_201_CREATED)
async def initiate_transfer(
    request: TransferRequestSchema,
    db: Session = Depends(get_db)
):
    """
    Initiate a privacy-compliant transfer through VettedPay multi-rail infrastructure.
    
    Security:
    - Backend NEVER sees plaintext bank details (encrypted client-side)
    - ZK-proof verified without revealing identity
    - Transaction logged with DIDs only
    - Idempotency key prevents duplicates
    
    Flow:
    1. Verify ZK-proof of non-sanction
    2. Create transaction record
    3. Route to active payment rail
    4. Return transaction ID and status
    """
    try:
        logger.info(
            f"Transfer request: {request.amount} {request.currency} "
            f"from {request.sender_did} to {request.recipient_did}"
        )
        
        # Initialize transaction engine with database session
        # TODO: Load active provider from config/environment
        engine = VettedPayTransactionEngine(
            active_provider="airwallex",  # or load from config
            provider_config={
                "api_url": "https://api.airwallex.com",
                "api_token": "mock_token",  # TODO: Load from env
            },
            db_session=db,
        )
        
        # Process transfer
        result = await engine.process_transfer(
            sender_did=request.sender_did,
            recipient_did=request.recipient_did,
            zk_proof=request.zk_proof.dict(),
            encrypted_compliance_packet=request.encrypted_compliance_packet,
            amount=request.amount,
            currency=request.currency,
            destination_account=request.destination_account,
            metadata=request.metadata,
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Transfer failed")
            )
        
        return TransferResponseSchema(
            success=True,
            transaction_id=result["transaction_id"],
            idempotency_key=result["idempotency_key"],
            status=result["status"],
            rail=result["rail"],
            amount=result["amount"],
            currency=result["currency"],
            compliance_verified=result.get("compliance_verified", False),
            created_at=datetime.utcnow().isoformat(),
            message="Transfer initiated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transfer initiation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer processing error: {str(e)}"
        )


@router.get("/transactions/{transaction_id}", response_model=TransactionDetailSchema)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific transaction.
    
    Privacy: Only returns non-sensitive data (DIDs, amounts, status).
    Does NOT return encrypted compliance packet or PII.
    """
    transaction = db.query(VettedPayTransaction).filter(
        VettedPayTransaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return TransactionDetailSchema(
        id=str(transaction.id),
        sender_did=transaction.sender_did,
        recipient_did=transaction.recipient_did,
        amount=str(transaction.amount),
        currency=transaction.currency,
        status=transaction.status.value,
        rail=transaction.active_rail.value,
        zk_proof_verified=transaction.zk_proof_verified,
        rail_transaction_id=transaction.rail_transaction_id,
        error_log=transaction.error_log,
        created_at=transaction.created_at.isoformat(),
        updated_at=transaction.updated_at.isoformat(),
    )


@router.get("/transactions/", response_model=list[TransactionDetailSchema])
def list_transactions(
    sender_did: Optional[str] = None,
    recipient_did: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List transactions with optional filtering.
    
    Query params:
    - sender_did: Filter by sender
    - recipient_did: Filter by recipient
    - status: Filter by status (initiated, settled, failed, etc.)
    - limit: Max results (default 50)
    - offset: Pagination offset (default 0)
    """
    query = db.query(VettedPayTransaction)
    
    if sender_did:
        query = query.filter(VettedPayTransaction.sender_did == sender_did)
    
    if recipient_did:
        query = query.filter(VettedPayTransaction.recipient_did == recipient_did)
    
    if status:
        try:
            status_enum = TransactionStatus[status.upper()]
            query = query.filter(VettedPayTransaction.status == status_enum)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )
    
    query = query.order_by(VettedPayTransaction.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    transactions = query.all()
    
    return [
        TransactionDetailSchema(
            id=str(t.id),
            sender_did=t.sender_did,
            recipient_did=t.recipient_did,
            amount=str(t.amount),
            currency=t.currency,
            status=t.status.value,
            rail=t.active_rail.value,
            zk_proof_verified=t.zk_proof_verified,
            rail_transaction_id=t.rail_transaction_id,
            error_log=t.error_log,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
        )
        for t in transactions
    ]


# ============================================================================
# Rail Health Endpoints
# ============================================================================

@router.get("/rails/health", response_model=list[RailHealthSchema])
def get_all_rail_health(db: Session = Depends(get_db)):
    """
    Get health status of all payment rails.
    
    Public endpoint for transparency.
    Shows real-time availability of Airwallex, Nium, Wise, etc.
    """
    rails = db.query(VettedPayRailHealth).all()
    
    return [
        RailHealthSchema(
            rail=r.rail.value,
            is_healthy=r.is_healthy,
            circuit_status=r.circuit_status,
            failure_count=r.failure_count,
            last_success_at=r.last_success_at.isoformat() if r.last_success_at else None,
            last_failure_at=r.last_failure_at.isoformat() if r.last_failure_at else None,
            error_message=r.error_message,
        )
        for r in rails
    ]


@router.get("/rails/{rail_name}/health", response_model=RailHealthSchema)
def get_rail_health(rail_name: str, db: Session = Depends(get_db)):
    """Get health status of a specific payment rail."""
    try:
        rail_enum = PaymentRail[rail_name.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rail not found: {rail_name}"
        )
    
    rail_health = db.query(VettedPayRailHealth).filter(
        VettedPayRailHealth.rail == rail_enum
    ).first()
    
    if not rail_health:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Health record not found for rail: {rail_name}"
        )
    
    return RailHealthSchema(
        rail=rail_health.rail.value,
        is_healthy=rail_health.is_healthy,
        circuit_status=rail_health.circuit_status,
        failure_count=rail_health.failure_count,
        last_success_at=rail_health.last_success_at.isoformat() if rail_health.last_success_at else None,
        last_failure_at=rail_health.last_failure_at.isoformat() if rail_health.last_failure_at else None,
        error_message=rail_health.error_message,
    )


# ============================================================================
# Waitlist Endpoints
# ============================================================================

@router.post("/waitlist", status_code=status.HTTP_201_CREATED)
def join_waitlist(
    signup: WaitlistSignupSchema,
    db: Session = Depends(get_db)
):
    """
    Join the VettedPay early adopter waitlist.
    
    Auto-scoring:
    - Healthcare/fintech orgs: +10 priority
    - Detailed use case: +5 priority
    - Referral from existing user: +3 priority
    """
    # Check for duplicate email
    existing = db.query(VettedPayWaitlist).filter(
        VettedPayWaitlist.email == signup.email
    ).first()
    
    if existing:
        return {
            "success": True,
            "message": "You're already on the waitlist!",
            "position": existing.priority_score
        }
    
    # Calculate priority score
    priority = 0
    if signup.organization:
        org_lower = signup.organization.lower()
        if any(keyword in org_lower for keyword in ['health', 'care', 'medical', 'fintech', 'bank']):
            priority += 10
    
    if signup.use_case and len(signup.use_case) > 50:
        priority += 5
    
    if signup.referral_source and signup.referral_source != 'organic':
        priority += 3
    
    # Create waitlist entry
    waitlist_entry = VettedPayWaitlist(
        email=signup.email,
        full_name=signup.full_name,
        organization=signup.organization,
        use_case=signup.use_case,
        referral_source=signup.referral_source,
        priority_score=priority,
        status='pending',
    )
    
    db.add(waitlist_entry)
    db.commit()
    db.refresh(waitlist_entry)
    
    # Calculate position in queue
    position = db.query(VettedPayWaitlist).filter(
        VettedPayWaitlist.priority_score >= priority,
        VettedPayWaitlist.status == 'pending'
    ).count()
    
    logger.info(f"New waitlist signup: {signup.email} (priority: {priority}, position: {position})")
    
    return {
        "success": True,
        "message": f"Welcome to VettedPay! You're #{position} on the waitlist.",
        "priority_score": priority,
        "position": position,
        "email": signup.email
    }
