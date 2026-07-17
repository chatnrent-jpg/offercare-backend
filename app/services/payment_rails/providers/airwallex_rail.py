"""
Airwallex-specific implementation of the VettedPay transaction rail.
Fallback-safe wrapper with idempotency and compliance packet support.
"""

import httpx
from typing import Dict, Any
from ..payout_adapter import PayoutProviderAdapter, PayoutResult, PayoutRail, PayoutStatus


class AirwallexRail(PayoutProviderAdapter):
    """
    Airwallex-specific implementation of the VettedPay transaction rail.
    If you add a new provider later, simply create a new file matching PayoutProviderAdapter rules.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url", "https://api.airwallex.com")
        self.api_token = config.get("api_token")
    
    def _get_rail_type(self) -> PayoutRail:
        return PayoutRail.AIRWALLEX
    
    async def execute_payout(
        self, 
        amount: float, 
        currency: str, 
        destination: str, 
        compliance_packet: str,
        idempotency_key: str,
        metadata: Dict[str, Any] = None
    ) -> PayoutResult:
        """
        Execute payout via Airwallex with compliance packet.
        
        Args:
            amount: Transfer amount
            currency: ISO currency code
            destination: Beneficiary ID
            compliance_packet: Encrypted compliance payload (Airwallex receives blind data)
            idempotency_key: Unique key to prevent duplicate transfers
            metadata: Optional additional data
            
        Returns:
            PayoutResult with transaction details
        """
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key
        }
        
        payload = {
            "source_amount": amount,
            "source_currency": currency,
            "payment_method": "local_clearing",
            "beneficiary_id": destination,
            # Airwallex receives the blind payload encrypted directly for them
            "compliance_packet": compliance_packet 
        }
        
        # Add metadata if provided
        if metadata:
            payload["reference"] = metadata.get("reference", idempotency_key)
            payload["reason"] = metadata.get("reason", "Payment for services")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/payouts/create", 
                    json=payload, 
                    headers=headers,
                    timeout=10.0
                )
                
                result = response.json()
                
                if response.status_code != 200:
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
                        error_message=result.get("message", "Rail execution failure")
                    )
                
                return PayoutResult(
                    success=True,
                    transaction_id=result.get("id", idempotency_key),
                    rail=PayoutRail.AIRWALLEX,
                    status=PayoutStatus.PROCESSING,
                    amount=amount,
                    currency=currency,
                    destination=destination,
                    compliance_verified=True,
                    provider_reference=result.get("id"),
                    metadata=result
                )
                
            except httpx.RequestError as exc:
                return PayoutResult(
                    success=False,
                    transaction_id=idempotency_key,
                    rail=PayoutRail.AIRWALLEX,
                    status=PayoutStatus.FAILED,
                    amount=amount,
                    currency=currency,
                    destination=destination,
                    compliance_verified=False,
                    error_code="CONNECTION_ERROR",
                    error_message=f"Connection error to financial rail: {str(exc)}"
                )
    
    async def check_payout_status(self, transaction_id: str) -> PayoutResult:
        """Check status of existing payout"""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/payouts/{transaction_id}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return PayoutResult(
                        success=False,
                        transaction_id=transaction_id,
                        rail=PayoutRail.AIRWALLEX,
                        status=PayoutStatus.FAILED,
                        amount=0.0,
                        currency="USD",
                        destination="unknown",
                        compliance_verified=False,
                        error_code=str(response.status_code),
                        error_message="Failed to check payout status"
                    )
                
                result = response.json()
                
                # Map Airwallex status to our unified status
                status_map = {
                    "CREATED": PayoutStatus.PENDING,
                    "PROCESSING": PayoutStatus.PROCESSING,
                    "COMPLETED": PayoutStatus.COMPLETED,
                    "FAILED": PayoutStatus.FAILED,
                    "CANCELLED": PayoutStatus.CANCELLED
                }
                
                return PayoutResult(
                    success=result.get("status") == "COMPLETED",
                    transaction_id=transaction_id,
                    rail=PayoutRail.AIRWALLEX,
                    status=status_map.get(result.get("status"), PayoutStatus.PENDING),
                    amount=result.get("source_amount", 0.0),
                    currency=result.get("source_currency", "USD"),
                    destination=result.get("beneficiary_id", "unknown"),
                    compliance_verified=True,
                    provider_reference=transaction_id,
                    metadata=result
                )
                
            except httpx.RequestError:
                return PayoutResult(
                    success=False,
                    transaction_id=transaction_id,
                    rail=PayoutRail.AIRWALLEX,
                    status=PayoutStatus.FAILED,
                    amount=0.0,
                    currency="USD",
                    destination="unknown",
                    compliance_verified=False,
                    error_code="CONNECTION_ERROR",
                    error_message="Connection error while checking status"
                )
    
    async def cancel_payout(self, transaction_id: str) -> PayoutResult:
        """Cancel pending payout"""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/payouts/{transaction_id}/cancel",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return PayoutResult(
                        success=True,
                        transaction_id=transaction_id,
                        rail=PayoutRail.AIRWALLEX,
                        status=PayoutStatus.CANCELLED,
                        amount=result.get("source_amount", 0.0),
                        currency=result.get("source_currency", "USD"),
                        destination=result.get("beneficiary_id", "unknown"),
                        compliance_verified=True,
                        metadata=result
                    )
                else:
                    # If cancel fails, return current status
                    return await self.check_payout_status(transaction_id)
                    
            except httpx.RequestError as exc:
                return PayoutResult(
                    success=False,
                    transaction_id=transaction_id,
                    rail=PayoutRail.AIRWALLEX,
                    status=PayoutStatus.FAILED,
                    amount=0.0,
                    currency="USD",
                    destination="unknown",
                    compliance_verified=False,
                    error_code="CONNECTION_ERROR",
                    error_message=f"Connection error: {str(exc)}"
                )
    
    async def verify_destination(
        self, 
        destination: str, 
        currency: str
    ) -> Dict[str, Any]:
        """Verify beneficiary account"""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/beneficiaries/{destination}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 404:
                    return {
                        "valid": False,
                        "error": "Beneficiary not found"
                    }
                
                if response.status_code != 200:
                    return {
                        "valid": False,
                        "error": "Failed to verify beneficiary"
                    }
                
                result = response.json()
                
                return {
                    "valid": True,
                    "beneficiary_id": result.get("id"),
                    "account_name": result.get("account_name"),
                    "bank_name": result.get("bank_details", {}).get("bank_name"),
                    "supported_currencies": result.get("supported_currencies", [])
                }
                
            except httpx.RequestError as exc:
                return {
                    "valid": False,
                    "error": f"Connection error: {str(exc)}"
                }
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        amount: float = None
    ) -> Dict[str, Any]:
        """Get current FX rate"""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "source_currency": from_currency,
            "target_currency": to_currency
        }
        
        if amount:
            params["source_amount"] = amount
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/rates/current",
                    headers=headers,
                    params=params,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return {
                        "error": "Failed to get exchange rate"
                    }
                
                result = response.json()
                
                return {
                    "rate": result.get("exchange_rate"),
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "source_amount": amount,
                    "target_amount": result.get("target_amount"),
                    "fee": result.get("fee")
                }
                
            except httpx.RequestError as exc:
                return {
                    "error": f"Connection error: {str(exc)}"
                }
