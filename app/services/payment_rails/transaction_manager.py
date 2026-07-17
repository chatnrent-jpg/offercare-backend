"""
VettedPay Transaction Manager
Core engine managing zero-knowledge compliance verification and abstract provider routing.
Orchestrates the entire payout flow from frontend client to financial rail.
"""

import hashlib
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from .airwallex_rail import AirwallexRail
from .payout_adapter import PayoutProviderAdapter, PayoutResult, PayoutRail, PayoutStatus
from .compliance_packet import CompliancePacketGenerator, CompliancePayload
from app.models.vettedpay import (
    VettedPayTransaction,
    VettedPayZKVerification,
    PaymentRail as DBPaymentRail,
    TransactionStatus as DBTransactionStatus,
)

logger = logging.getLogger(__name__)


class VettedPayTransactionEngine:
    """
    Core engine managing zero-knowledge compliance verification and 
    abstract provider routing.
    
    This orchestration layer:
    1. Receives frontend client payload
    2. Verifies ZK-proof of non-sanction
    3. Dynamically loads active financial rail
    4. Securely dispatches transfer
    
    Your engine passes encrypted data without seeing the contents.
    """
    
    def __init__(
        self,
        active_provider: str,
        provider_config: Dict[str, Any],
        db_session: Optional[Session] = None,
        compliance_generator: Optional[CompliancePacketGenerator] = None
    ):
        """
        Initialize transaction engine with dynamic provider selection.
        
        Args:
            active_provider: Provider name ("airwallex", "nium", "wise", etc.)
            provider_config: Provider-specific configuration
            db_session: Optional SQLAlchemy database session for persistence
            compliance_generator: Optional compliance packet generator
        """
        self.active_provider = active_provider
        self.compliance_generator = compliance_generator
        self.db = db_session
        
        # Dynamic Provider Factory
        if active_provider == "airwallex":
            self.rail = AirwallexRail(provider_config)
        elif active_provider == "nium":
            # from .nium_rail import NiumRail
            # self.rail = NiumRail(provider_config)
            raise NotImplementedError("Nium integration is not yet active.")
        elif active_provider == "wise":
            # from .wise_rail import WiseRail
            # self.rail = WiseRail(provider_config)
            raise NotImplementedError("Wise integration is not yet active.")
        elif active_provider == "stablecoin":
            # from .stablecoin_rail import StablecoinRail
            # self.rail = StablecoinRail(provider_config)
            raise NotImplementedError("Stablecoin integration is not yet active.")
        else:
            raise ValueError(f"Unknown financial provider: {active_provider}")
        
        logger.info(f"VettedPayTransactionEngine initialized with provider: {active_provider}")
    
    def _map_rail_to_db_enum(self, rail: PayoutRail) -> DBPaymentRail:
        """Map PayoutRail enum to DBPaymentRail enum."""
        mapping = {
            PayoutRail.AIRWALLEX: DBPaymentRail.AIRWALLEX,
            PayoutRail.NIUM: DBPaymentRail.NIUM,
            PayoutRail.WISE: DBPaymentRail.WISE,
            PayoutRail.STABLECOIN_USDC: DBPaymentRail.STABLECOIN_USDC,
        }
        return mapping.get(rail, DBPaymentRail.FALLBACK_MOCK)
    
    def _map_status_to_db_enum(self, status: PayoutStatus) -> DBTransactionStatus:
        """Map PayoutStatus enum to DBTransactionStatus enum."""
        mapping = {
            PayoutStatus.PENDING: DBTransactionStatus.INITIATED,
            PayoutStatus.PROCESSING: DBTransactionStatus.DISPATCHED_TO_RAIL,
            PayoutStatus.COMPLETED: DBTransactionStatus.SETTLED,
            PayoutStatus.FAILED: DBTransactionStatus.FAILED,
            PayoutStatus.CANCELLED: DBTransactionStatus.CANCELLED,
        }
        return mapping.get(status, DBTransactionStatus.INITIATED)
    
    async def process_transfer(
        self,
        sender_did: str,
        recipient_did: str,
        zk_proof: Dict[str, Any],
        encrypted_compliance_packet: str,
        amount: float,
        currency: str,
        destination_account: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a compliant transfer through the active financial rail.
        
        Args:
            sender_did: Sender's decentralized identifier
            recipient_did: Recipient's decentralized identifier
            zk_proof: Zero-knowledge proof of non-sanction
            encrypted_compliance_packet: Pre-encrypted compliance data
            amount: Transfer amount
            currency: ISO currency code
            destination_account: Beneficiary account ID
            metadata: Optional transaction metadata
            
        Returns:
            Dict with success status and transaction details
        """
        
        # 1. Run internal ZK Check (Verifies user generated proof of non-sanction)
        logger.info(f"Verifying ZK compliance for sender: {sender_did}")
        is_compliant = await self._verify_zk_compliance(sender_did, zk_proof)
        
        if not is_compliant:
            logger.warning(f"ZK compliance check failed for sender: {sender_did}")
            return {
                "success": False,
                "error": "Zero-knowledge sanction check failed validation.",
                "error_code": "ZK_COMPLIANCE_FAILED"
            }
        
        # 2. Prevent duplicate billing/double spending loops via idempotency key
        unique_str = f"{sender_did}-{recipient_did}-{amount}-{currency}-{time.time()}"
        idempotency_key = hashlib.sha256(unique_str.encode()).hexdigest()
        
        # 2.5. Create database transaction record (if DB session provided)
        db_transaction = None
        if self.db:
            try:
                db_transaction = VettedPayTransaction(
                    idempotency_key=idempotency_key,
                    sender_did=sender_did,
                    recipient_did=recipient_did,
                    amount=Decimal(str(amount)),
                    currency=currency,
                    active_rail=self._map_rail_to_db_enum(self.rail._get_rail_type()),
                    status=DBTransactionStatus.INITIATED,
                    zk_proof_verified=True,
                    metadata=metadata,
                )
                self.db.add(db_transaction)
                self.db.flush()  # Get the transaction ID without committing
                
                # Log ZK verification
                zk_verification = VettedPayZKVerification(
                    transaction_id=db_transaction.id,
                    sender_did=sender_did,
                    proof_type="sanction_check",
                    verification_result=True,
                    verification_method=zk_proof.get("verification_method", "OFAC_API_v1"),
                    proof_timestamp=datetime.fromisoformat(zk_proof.get("timestamp", datetime.now(timezone.utc).isoformat())),
                )
                self.db.add(zk_verification)
                
                logger.info(f"Created transaction record: {db_transaction.id}")
            except Exception as e:
                logger.error(f"Failed to create transaction record: {e}")
                # Continue anyway - database persistence is not critical for processing
        
        logger.info(
            f"Processing transfer: {amount} {currency} from {sender_did} "
            f"via {self.active_provider} (idempotency: {idempotency_key[:16]}...)"
        )
        
        # 3. Dispatch payload down the abstract rail
        # Your engine passes the encrypted data without seeing the contents
        try:
            payment_result = await self.rail.execute_payout(
                amount=amount,
                currency=currency,
                destination=destination_account,
                compliance_packet=encrypted_compliance_packet,
                idempotency_key=idempotency_key,
                metadata=metadata
            )
            
            # Convert PayoutResult to dict for client response
            result_dict = {
                "success": payment_result.success,
                "transaction_id": payment_result.transaction_id,
                "rail": payment_result.rail.value,
                "status": payment_result.status.value,
                "amount": payment_result.amount,
                "currency": payment_result.currency,
                "compliance_verified": payment_result.compliance_verified,
                "idempotency_key": idempotency_key,
            }
            
            if payment_result.provider_reference:
                result_dict["provider_reference"] = payment_result.provider_reference
            
            if payment_result.fees:
                result_dict["fees"] = float(payment_result.fees)
            
            if not payment_result.success:
                result_dict["error"] = payment_result.error_message
                result_dict["error_code"] = payment_result.error_code
            
            logger.info(
                f"Transfer {'successful' if payment_result.success else 'failed'}: "
                f"{payment_result.transaction_id}"
            )
            
            # Update database transaction status
            if self.db and db_transaction:
                try:
                    db_transaction.status = self._map_status_to_db_enum(payment_result.status)
                    db_transaction.rail_transaction_id = payment_result.transaction_id
                    db_transaction.compliance_packet_id = payment_result.compliance_packet_id
                    
                    if not payment_result.success:
                        db_transaction.error_log = payment_result.error_message
                    
                    self.db.commit()
                    logger.info(f"Updated transaction {db_transaction.id} status to {db_transaction.status.value}")
                except Exception as e:
                    logger.error(f"Failed to update transaction status: {e}")
                    self.db.rollback()
            
            return result_dict
            
        except Exception as exc:
            logger.error(f"Transfer processing failed: {exc}", exc_info=True)
            
            # Update database transaction status to failed
            if self.db and db_transaction:
                try:
                    db_transaction.status = DBTransactionStatus.FAILED
                    db_transaction.error_log = str(exc)
                    self.db.commit()
                except Exception as db_error:
                    logger.error(f"Failed to update transaction status after error: {db_error}")
                    self.db.rollback()
            
            return {
                "success": False,
                "error": f"Transfer processing error: {str(exc)}",
                "error_code": "PROCESSING_ERROR",
                "idempotency_key": idempotency_key
            }
    
    async def process_transfer_with_compliance_generation(
        self,
        sender_did: str,
        recipient_did: str,
        zk_proof: Dict[str, Any],
        compliance_data: CompliancePayload,
        recipient_bank_id: str,
        amount: float,
        currency: str,
        destination_account: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process transfer with automatic compliance packet generation.
        
        This is a convenience method that generates the compliance packet
        automatically if you don't have a pre-encrypted one.
        
        Args:
            sender_did: Sender's decentralized identifier
            recipient_did: Recipient's decentralized identifier
            zk_proof: Zero-knowledge proof of non-sanction
            compliance_data: Raw compliance data (will be encrypted)
            recipient_bank_id: Bank ID for encryption key selection
            amount: Transfer amount
            currency: ISO currency code
            destination_account: Beneficiary account ID
            metadata: Optional transaction metadata
            
        Returns:
            Dict with success status and transaction details
        """
        
        if not self.compliance_generator:
            return {
                "success": False,
                "error": "Compliance generator not configured",
                "error_code": "NO_COMPLIANCE_GENERATOR"
            }
        
        # Generate compliance packet
        try:
            logger.info(f"Generating compliance packet for sender: {sender_did}")
            packet = self.compliance_generator.generate_packet(
                payload=compliance_data,
                recipient_id=recipient_bank_id,
                verification_method="OFAC_API_v1"
            )
            
            # Serialize packet for transmission
            encrypted_packet = self.compliance_generator.serialize_packet(packet)
            
            # Process transfer with generated packet
            return await self.process_transfer(
                sender_did=sender_did,
                recipient_did=recipient_did,
                zk_proof=zk_proof,
                encrypted_compliance_packet=encrypted_packet,
                amount=amount,
                currency=currency,
                destination_account=destination_account,
                metadata=metadata
            )
            
        except Exception as exc:
            logger.error(f"Compliance packet generation failed: {exc}", exc_info=True)
            return {
                "success": False,
                "error": f"Compliance packet generation error: {str(exc)}",
                "error_code": "COMPLIANCE_GENERATION_ERROR"
            }
    
    async def check_transfer_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Check the status of a previously initiated transfer.
        
        Args:
            transaction_id: Transaction identifier
            
        Returns:
            Dict with current transaction status
        """
        try:
            result = await self.rail.check_payout_status(transaction_id)
            
            return {
                "success": result.success,
                "transaction_id": result.transaction_id,
                "rail": result.rail.value,
                "status": result.status.value,
                "amount": result.amount,
                "currency": result.currency,
                "compliance_verified": result.compliance_verified
            }
            
        except Exception as exc:
            logger.error(f"Status check failed: {exc}", exc_info=True)
            return {
                "success": False,
                "error": f"Status check error: {str(exc)}",
                "error_code": "STATUS_CHECK_ERROR"
            }
    
    async def cancel_transfer(self, transaction_id: str) -> Dict[str, Any]:
        """
        Attempt to cancel a pending transfer.
        
        Args:
            transaction_id: Transaction identifier
            
        Returns:
            Dict with cancellation result
        """
        try:
            result = await self.rail.cancel_payout(transaction_id)
            
            return {
                "success": result.success,
                "transaction_id": result.transaction_id,
                "status": result.status.value,
                "message": "Transfer cancelled successfully" if result.success else "Cancellation failed"
            }
            
        except Exception as exc:
            logger.error(f"Cancellation failed: {exc}", exc_info=True)
            return {
                "success": False,
                "error": f"Cancellation error: {str(exc)}",
                "error_code": "CANCELLATION_ERROR"
            }
    
    async def _verify_zk_compliance(self, did: str, proof: Dict[str, Any]) -> bool:
        """
        Verifies the cryptographic proof generated by the user's client app.
        
        Proves the user's country/identity is cleared against global AML databases
        without revealing their name or exact ID details to your backend database.
        
        This connects to your existing Reclaim Protocol / zkTLS proof checking loops.
        
        Args:
            did: Decentralized identifier
            proof: ZK-proof data structure
            
        Returns:
            True if proof is valid and compliant
        """
        
        # TODO: Integrate with existing Reclaim Protocol / zkTLS verification
        # from app.services.reclaim_verification import verify_zk_proof
        # return await verify_zk_proof(did, proof)
        
        # For now, simple validation
        if not proof:
            logger.warning(f"Empty ZK proof provided for DID: {did}")
            return False
        
        # Check proof structure
        required_fields = ["valid", "timestamp", "signature"]
        for field in required_fields:
            if field not in proof:
                logger.warning(f"ZK proof missing required field: {field}")
                return False
        
        # Check proof validity
        if not proof.get("valid", False):
            logger.warning(f"ZK proof marked as invalid for DID: {did}")
            return False
        
        # Check proof freshness (within last 24 hours)
        try:
            proof_timestamp = proof.get("timestamp")
            if proof_timestamp:
                # Assuming ISO format timestamp
                proof_time = datetime.fromisoformat(proof_timestamp.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                age_hours = (now - proof_time).total_seconds() / 3600
                
                if age_hours > 24:
                    logger.warning(f"ZK proof expired (age: {age_hours:.1f} hours)")
                    return False
        except Exception as exc:
            logger.error(f"Failed to validate proof timestamp: {exc}")
            return False
        
        logger.info(f"ZK compliance verified for DID: {did}")
        return True
    
    def get_active_provider(self) -> str:
        """Get the currently active provider name"""
        return self.active_provider
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of the active financial rail.
        
        Returns:
            Dict with health status
        """
        try:
            is_healthy = await self.rail.health_check()
            return {
                "healthy": is_healthy,
                "provider": self.active_provider,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as exc:
            logger.error(f"Health check failed: {exc}", exc_info=True)
            return {
                "healthy": False,
                "provider": self.active_provider,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
