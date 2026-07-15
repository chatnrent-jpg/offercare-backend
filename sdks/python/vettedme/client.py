"""VettedMe API Client"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx

from .models import (
    Passport,
    Badge,
    VerificationResult,
    PassportCreate,
    BadgeCreate,
    WebhookSubscription,
    APIKey,
)
from .exceptions import (
    VettedMeError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)


class Client:
    """
    VettedMe API Client
    
    Args:
        api_key: Your VettedMe API key (or set VETTEDME_API_KEY env var)
        base_url: API base URL (default: https://api.vettedme.ai)
        timeout: Request timeout in seconds (default: 30)
    
    Example:
        >>> client = Client(api_key="vm_live_...")
        >>> result = client.verify("PASS-ABC-123")
        >>> print(result.valid)
        True
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.vettedme.ai",
        timeout: int = 30,
    ):
        self.api_key = api_key or os.getenv("VETTEDME_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "API key required. Pass api_key= or set VETTEDME_API_KEY environment variable."
            )
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "vettedme-python/1.0.0",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    def close(self):
        """Close the HTTP client"""
        self._client.close()
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request and handle errors"""
        try:
            response = self._client.request(method, endpoint, **kwargs)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif response.status_code == 404:
                raise NotFoundError("Resource not found")
            elif response.status_code == 422:
                raise ValidationError(response.json().get("detail", "Validation error"))
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Upgrade your plan or try again later.")
            elif response.status_code >= 500:
                raise ServerError(f"Server error: {response.status_code}")
            else:
                raise VettedMeError(f"Unexpected error: {response.status_code} - {response.text}")
        
        except httpx.RequestError as e:
            raise VettedMeError(f"Request failed: {str(e)}")
    
    # ==================== VERIFICATION API (CORE) ====================
    
    def verify(self, passport_id: str, **kwargs) -> VerificationResult:
        """
        Verify a passport credential (instant verification)
        
        Args:
            passport_id: The passport ID (e.g., "PASS-ABC-123")
            **kwargs: Additional verification options
        
        Returns:
            VerificationResult object
        
        Example:
            >>> result = client.verify("PASS-ABC-123")
            >>> if result.valid:
            ...     print(f"✅ {result.full_name} - {result.trust_score}% trust")
        """
        data = self._request("POST", "/api/v1/passport/verify", json={
            "passport_id": passport_id,
            **kwargs
        })
        return VerificationResult(**data)
    
    def verify_badge(self, passport_id: str, badge_type: str) -> VerificationResult:
        """
        Verify a specific badge on a passport
        
        Args:
            passport_id: The passport ID
            badge_type: Badge type to verify (e.g., "HEALTHCARE", "SECURITY_CLEARANCE")
        
        Returns:
            VerificationResult object
        """
        data = self._request("POST", "/api/v1/passport/verify", json={
            "passport_id": passport_id,
            "badge_type": badge_type
        })
        return VerificationResult(**data)
    
    # ==================== PASSPORT MANAGEMENT ====================
    
    def create_passport(self, user_data: Dict[str, Any]) -> Passport:
        """
        Create a new passport for a user
        
        Args:
            user_data: User information (full_name, email, etc.)
        
        Returns:
            Passport object
        
        Example:
            >>> passport = client.create_passport({
            ...     "full_name": "Jane Smith",
            ...     "email": "jane@example.com",
            ...     "phone": "+1234567890"
            ... })
            >>> print(passport.id)
        """
        data = self._request("POST", "/api/v1/passport", json=user_data)
        return Passport(**data)
    
    def get_passport(self, passport_id: str) -> Passport:
        """Get passport details"""
        data = self._request("GET", f"/api/v1/passport/{passport_id}")
        return Passport(**data)
    
    def list_passports(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Passport]:
        """List all passports (for your organization)"""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        
        data = self._request("GET", "/api/v1/passport", params=params)
        return [Passport(**p) for p in data.get("passports", [])]
    
    def revoke_passport(self, passport_id: str, reason: str) -> Dict[str, Any]:
        """Revoke a passport"""
        return self._request("POST", f"/api/v1/passport/{passport_id}/revoke", json={
            "reason": reason
        })
    
    # ==================== BADGE MANAGEMENT ====================
    
    def add_badge(self, passport_id: str, badge_data: Dict[str, Any]) -> Badge:
        """
        Add a credential badge to a passport
        
        Args:
            passport_id: The passport ID
            badge_data: Badge information (type, credential_data, etc.)
        
        Returns:
            Badge object
        
        Example:
            >>> badge = client.add_badge("PASS-ABC-123", {
            ...     "type": "HEALTHCARE",
            ...     "credential_data": {
            ...         "license_type": "RN",
            ...         "license_number": "RN123456",
            ...         "state": "MD"
            ...     }
            ... })
        """
        data = self._request("POST", f"/api/v1/passport/{passport_id}/badges", json=badge_data)
        return Badge(**data)
    
    def get_badge(self, badge_id: str) -> Badge:
        """Get badge details"""
        data = self._request("GET", f"/api/v1/badges/{badge_id}")
        return Badge(**data)
    
    def revoke_badge(self, badge_id: str, reason: str) -> Dict[str, Any]:
        """Revoke a badge"""
        return self._request("POST", f"/api/v1/badges/{badge_id}/revoke", json={
            "reason": reason
        })
    
    # ==================== WEBHOOK MANAGEMENT ====================
    
    def create_webhook(self, url: str, events: List[str]) -> WebhookSubscription:
        """
        Create a webhook subscription
        
        Args:
            url: Your webhook endpoint URL
            events: List of events to subscribe to
        
        Returns:
            WebhookSubscription object
        
        Example:
            >>> webhook = client.create_webhook(
            ...     url="https://yourapp.com/webhooks/vettedme",
            ...     events=["credential.verified", "badge.revoked"]
            ... )
        """
        data = self._request("POST", "/api/v1/webhooks", json={
            "url": url,
            "events": events
        })
        return WebhookSubscription(**data)
    
    def list_webhooks(self) -> List[WebhookSubscription]:
        """List all webhook subscriptions"""
        data = self._request("GET", "/api/v1/webhooks")
        return [WebhookSubscription(**w) for w in data.get("webhooks", [])]
    
    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook subscription"""
        return self._request("DELETE", f"/api/v1/webhooks/{webhook_id}")
    
    # ==================== API KEY MANAGEMENT ====================
    
    def create_api_key(self, name: str, permissions: List[str]) -> APIKey:
        """Create a new API key"""
        data = self._request("POST", "/api/v1/api-keys", json={
            "name": name,
            "permissions": permissions
        })
        return APIKey(**data)
    
    def list_api_keys(self) -> List[APIKey]:
        """List all API keys"""
        data = self._request("GET", "/api/v1/api-keys")
        return [APIKey(**k) for k in data.get("keys", [])]
    
    def revoke_api_key(self, key_id: str) -> Dict[str, Any]:
        """Revoke an API key"""
        return self._request("DELETE", f"/api/v1/api-keys/{key_id}")
    
    # ==================== ANALYTICS ====================
    
    def get_usage_stats(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get usage statistics"""
        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        
        return self._request("GET", "/api/v1/analytics/usage", params=params)


# Async client for high-performance applications
class AsyncClient(Client):
    """Async version of VettedMe Client (for asyncio applications)"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "vettedme-python/1.0.0",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
    
    async def verify(self, passport_id: str, **kwargs) -> VerificationResult:
        """Async verify"""
        response = await self._client.post("/api/v1/passport/verify", json={
            "passport_id": passport_id,
            **kwargs
        })
        return VerificationResult(**response.json())
    
    async def close(self):
        """Close the async HTTP client"""
        await self._client.aclose()
