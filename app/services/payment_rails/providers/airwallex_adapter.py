"""
Airwallex Payment Rail Adapter
Concrete implementation for Airwallex cross-border transfers.
"""

import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from ..payout_adapter import (
    PayoutProviderAdapter,
    PayoutRail,
    PayoutStatus,
    PayoutResult,
    ComplianceVerificationError,
    InsufficientFundsError,
    InvalidDestinationError,
    RateLimitError,
)
from ..compliance_packet import CompliancePacketGenerator


class AirwallexAdapter(PayoutProviderAdapter):
    """
    Airwallex payment rail implementation.
    
    Features:
    - Global account payouts
    - Multi-currency support
    - Real-time FX rates
    - Compliance packet attachment
    """
    
    BASE_URL_SANDBOX = "https://api-demo.airwallex.com"
    BASE_URL_PRODUCTION = "https://api.airwallex.com"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.client_id = config.get('client_id')
        self.base_url = (
            self.BASE_URL_PRODUCTION 
            if config.get('environment') == 'production' 
            else self.BASE_URL_SANDBOX
        )
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
    def _get_rail_type(self) -> PayoutRail:
        return PayoutRail.AIRWALLEX
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if self._access_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at:
                return
        
        # Authenticate
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/authentication/login",
                headers={"Content-Type": "application/json"},
                json={
                    "x-client-id": self.client_id,
                    "x-api-key": self.api_key,
                    "x-api-secret": self.api_secret
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Airwallex authentication failed: {response.text}")
            
            data = response.json()
            self._access_token = data['token']
            # Token valid for 1 hour, refresh 5 minutes early
            self._token_expires_at = datetime.now(timezone.utc).replace(
                minute=datetime.now().minute + 55
            )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated request headers"""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "x-client-id": self.client_id
        }
    
    async def execute_payout(
        self,
        amount: float,
        currency: str,
        destination: str,
        compliance_packet: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PayoutResult:
        """Execute payout via Airwallex"""
        await self._ensure_authenticated()
        
        # Parse destination (can be beneficiary_id or account details)
        beneficiary_id = destination
        
        payout_payload = {
            "request_id": idempotency_key,
            "source_currency": currency,
            "source_amount": amount,
            "beneficiary_id": beneficiary_id,
            "reason": metadata.get("reason", "Payment for services") if metadata else "Payment for services",
            "reference": metadata.get("reference", idempotency_key) if metadata else idempotency_key,
            "compliance_packet": compliance_packet,  # Attached to transaction
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/transfers/create",
                    headers=self._get_headers(),
                    json=payout_payload,
                    timeout=30.0
                )
                
                if response.status_code == 401:
                    raise ComplianceVerificationError("Compliance packet verification failed")
                elif response.status_code == 402:
                    raise InsufficientFundsError("Insufficient account balance")
                elif response.status_code == 404:
                    raise InvalidDestinationError(f"Beneficiary not found: {beneficiary_id}")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded")
                elif response.status_code != 200:
                    return PayoutResult(
                        success=False,
                        transaction_id=idempotency_key,
                        rail=PayoutRail.AIRWALLEX,
                        status=PayoutStatus.FAILED,
                        amount=amount,
                        currency=currency,
                        destination=destination,
                        compliance_verified=False,
                        error_code=str(response.status_code),
                        error_message=response.text
                    )
                
                data = response.json()
                
                # Map Airwallex status to our unified status
                status_map = {
                    "CREATED": PayoutStatus.PENDING,
                    "PROCESSING": PayoutStatus.PROCESSING,
                    "COMPLETED": PayoutStatus.COMPLETED,
                    "FAILED": PayoutStatus.FAILED,
                    "CANCELLED": PayoutStatus.CANCELLED
                }
                
                return PayoutResult(
                    success=True,
                    transaction_id=data.get("id", idempotency_key),
                    rail=PayoutRail.AIRWALLEX,
                    status=status_map.get(data.get("status"), PayoutStatus.PENDING),
                    amount=amount,
                    currency=currency,
                    destination=destination,
                    compliance_verified=True,
                    provider_reference=data.get("id"),
                    fees=data.get("fee", {}).get("amount"),
                    metadata=data
                )
                
        except httpx.TimeoutException:
            return PayoutResult(
                success=False,
                transaction_id=idempotency_key,
                rail=PayoutRail.AIRWALLEX,
                status=PayoutStatus.FAILED,
                amount=amount,
                currency=currency,
                destination=destination,
                compliance_verified=False,
                error_code="TIMEOUT",
                error_message="Request timed out"
            )
    
    async def check_payout_status(self, transaction_id: str) -> PayoutResult:
        """Check status of existing payout"""
        await self._ensure_authenticated()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/transfers/{transaction_id}",
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to check status: {response.text}")
            
            data = response.json()
            
            status_map = {
                "CREATED": PayoutStatus.PENDING,
                "PROCESSING": PayoutStatus.PROCESSING,
                "COMPLETED": PayoutStatus.COMPLETED,
                "FAILED": PayoutStatus.FAILED,
                "CANCELLED": PayoutStatus.CANCELLED
            }
            
            return PayoutResult(
                success=data.get("status") == "COMPLETED",
                transaction_id=transaction_id,
                rail=PayoutRail.AIRWALLEX,
                status=status_map.get(data.get("status"), PayoutStatus.PENDING),
                amount=data.get("source_amount"),
                currency=data.get("source_currency"),
                destination=data.get("beneficiary_id"),
                compliance_verified=True,
                provider_reference=transaction_id,
                metadata=data
            )
    
    async def cancel_payout(self, transaction_id: str) -> PayoutResult:
        """Cancel pending payout"""
        await self._ensure_authenticated()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/transfers/{transaction_id}/cancel",
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                # Already processed, cannot cancel
                status_result = await self.check_payout_status(transaction_id)
                return status_result
            
            data = response.json()
            
            return PayoutResult(
                success=True,
                transaction_id=transaction_id,
                rail=PayoutRail.AIRWALLEX,
                status=PayoutStatus.CANCELLED,
                amount=data.get("source_amount"),
                currency=data.get("source_currency"),
                destination=data.get("beneficiary_id"),
                compliance_verified=True,
                provider_reference=transaction_id,
                metadata=data
            )
    
    async def verify_destination(
        self, 
        destination: str, 
        currency: str
    ) -> Dict[str, Any]:
        """Verify beneficiary account"""
        await self._ensure_authenticated()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/beneficiaries/{destination}",
                headers=self._get_headers()
            )
            
            if response.status_code == 404:
                return {
                    "valid": False,
                    "error": "Beneficiary not found"
                }
            
            if response.status_code != 200:
                return {
                    "valid": False,
                    "error": response.text
                }
            
            data = response.json()
            
            return {
                "valid": True,
                "beneficiary_id": data.get("id"),
                "account_name": data.get("account_name"),
                "bank_name": data.get("bank_details", {}).get("bank_name"),
                "supported_currencies": data.get("supported_currencies", [])
            }
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Get current FX rate"""
        await self._ensure_authenticated()
        
        params = {
            "source_currency": from_currency,
            "target_currency": to_currency
        }
        
        if amount:
            params["source_amount"] = amount
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/rates/current",
                headers=self._get_headers(),
                params=params
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get exchange rate: {response.text}")
            
            data = response.json()
            
            return {
                "rate": data.get("exchange_rate"),
                "from_currency": from_currency,
                "to_currency": to_currency,
                "source_amount": amount,
                "target_amount": data.get("target_amount"),
                "fee": data.get("fee"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
