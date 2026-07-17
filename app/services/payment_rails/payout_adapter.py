"""
VettedPay Multi-Rail Financial Adapter
Abstract interface for payment provider independence using the Adapter Pattern.
Ensures zero platform lock-in across Airwallex, Nium, Wise, and on-chain rails.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class PayoutStatus(Enum):
    """Unified payout status across all rails"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_ACTION = "requires_action"


class PayoutRail(Enum):
    """Supported financial rails"""
    AIRWALLEX = "airwallex"
    NIUM = "nium"
    WISE = "wise"
    STABLECOIN = "stablecoin"
    STRIPE = "stripe"


@dataclass
class PayoutResult:
    """Standardized payout response across all providers"""
    success: bool
    transaction_id: str
    rail: PayoutRail
    status: PayoutStatus
    amount: float
    currency: str
    destination: str
    compliance_verified: bool
    provider_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    estimated_arrival: Optional[datetime] = None
    fees: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class PayoutProviderAdapter(ABC):
    """
    Abstract Interface for VettedPay Financial Rails.
    Implements the Adapter Pattern to eliminate platform lock-in.
    
    Design Principles:
    - Provider-agnostic core logic
    - Fail-over capability between rails
    - Compliance packet verification
    - Idempotent operations
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider adapter with configuration.
        
        Args:
            config: Provider-specific configuration including:
                - api_key: Provider API credentials
                - api_secret: Provider secret key
                - environment: 'sandbox' or 'production'
                - webhook_secret: Optional webhook verification secret
                - default_currency: Default currency for operations
        """
        self.config = config
        self.rail = self._get_rail_type()
        self.environment = config.get('environment', 'sandbox')
        
    @abstractmethod
    def _get_rail_type(self) -> PayoutRail:
        """Return the rail type for this adapter"""
        pass

    @abstractmethod
    async def execute_payout(
        self, 
        amount: float, 
        currency: str, 
        destination: str, 
        compliance_packet: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PayoutResult:
        """
        Executes a cross-border transfer with compliance verification.
        
        Args:
            amount: Transfer amount in the specified currency
            currency: ISO 4217 currency code (USD, EUR, GBP, etc.)
            destination: Recipient account identifier (IBAN, account number, wallet address)
            compliance_packet: Encrypted compliance payload with ZK-proof of non-sanction
            idempotency_key: Unique key to prevent duplicate transfers
            metadata: Optional additional data for the transfer
            
        Returns:
            PayoutResult with transaction details and status
            
        Raises:
            ComplianceVerificationError: If compliance packet is invalid
            InsufficientFundsError: If account balance is too low
            InvalidDestinationError: If destination account is invalid
        """
        pass

    @abstractmethod
    async def check_payout_status(
        self, 
        transaction_id: str
    ) -> PayoutResult:
        """
        Check the status of a previously initiated payout.
        
        Args:
            transaction_id: Internal transaction identifier
            
        Returns:
            PayoutResult with current status
        """
        pass

    @abstractmethod
    async def cancel_payout(
        self, 
        transaction_id: str
    ) -> PayoutResult:
        """
        Attempt to cancel a pending payout.
        
        Args:
            transaction_id: Internal transaction identifier
            
        Returns:
            PayoutResult with cancellation status
        """
        pass

    @abstractmethod
    async def verify_destination(
        self, 
        destination: str, 
        currency: str
    ) -> Dict[str, Any]:
        """
        Verify that a destination account is valid for payouts.
        
        Args:
            destination: Recipient account identifier
            currency: Currency for the transfer
            
        Returns:
            Dict with verification status and account details
        """
        pass

    @abstractmethod
    async def get_exchange_rate(
        self, 
        from_currency: str, 
        to_currency: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get current exchange rate between currencies.
        
        Args:
            from_currency: Source currency code
            to_currency: Destination currency code
            amount: Optional amount for accurate quote including fees
            
        Returns:
            Dict with exchange rate and fee information
        """
        pass

    async def health_check(self) -> bool:
        """
        Verify provider API connectivity and credentials.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            # Default implementation - can be overridden
            result = await self.get_exchange_rate("USD", "EUR", 100.0)
            return result is not None
        except Exception:
            return False


class PayoutProviderError(Exception):
    """Base exception for payout provider errors"""
    pass


class ComplianceVerificationError(PayoutProviderError):
    """Raised when compliance packet verification fails"""
    pass


class InsufficientFundsError(PayoutProviderError):
    """Raised when account balance is insufficient"""
    pass


class InvalidDestinationError(PayoutProviderError):
    """Raised when destination account is invalid"""
    pass


class RateLimitError(PayoutProviderError):
    """Raised when provider rate limit is exceeded"""
    pass
