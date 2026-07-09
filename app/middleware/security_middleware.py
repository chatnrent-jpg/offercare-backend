"""
Security Middleware — API Protection & Scraper Defense

Sprint: VCAI-TIER4-SECURITY-2026-07-07
Purpose: Protect APIs from scrapers, competitors, and malicious actors.

Protection Layers:
1. Rate Limiting (per IP, per user)
2. Bot Detection (User-Agent analysis)
3. Scraper Traps (Decoy endpoints + honeypots)
4. IP Reputation Scoring
5. Request Pattern Analysis

Defense Strategy:
- Legitimate users: Normal service
- Suspicious activity: Rate limited + logged
- Confirmed scrapers: Banned + served decoy data
- Competitor bots: Permanently blocked
"""

import hashlib
import json
import time
from typing import Dict, Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis import Redis
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import IPWhitelist
from app.services.security_evidence_ledger import log_security_violation


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Multi-layer security middleware for API protection.
    """
    
    def __init__(self, app, redis_client: Optional[Redis] = None):
        super().__init__(app)
        self.redis = redis_client
        self.suspicious_ips = set()
        self.banned_ips = set()
        
        # Scraper User-Agent patterns
        self.scraper_patterns = [
            'scrapy', 'beautifulsoup', 'curl', 'wget', 'python-requests',
            'bot', 'crawler', 'spider', 'scraper'
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security layers."""
        
        # Layer 0: IP Whitelist check (NEW - prevents false positives)
        client_ip = self._get_client_ip(request)
        
        is_whitelisted = await self._is_whitelisted(client_ip)
        if is_whitelisted:
            # Skip all security checks for whitelisted IPs
            response = await call_next(request)
            return self._add_security_headers(response)
        
        # Layer 1: Banned IP check
        if client_ip in self.banned_ips:
            await self._log_to_evidence_ledger(
                "BANNED_IP_ACCESS",
                {"ip": client_ip, "path": request.url.path},
                client_ip,
                request.headers.get("user-agent")
            )
            return self._serve_decoy_response()
        
        # Layer 2: Rate limit check
        if self._is_rate_limited(client_ip):
            await self._log_to_evidence_ledger(
                "RATE_LIMIT_VIOLATION",
                {"ip": client_ip, "path": request.url.path, "limit": 100},
                client_ip,
                request.headers.get("user-agent")
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "Rate limit exceeded"}
            )
        
        # Layer 3: Bot/scraper detection
        user_agent = request.headers.get("user-agent", "").lower()
        if self._is_scraper(user_agent):
            self.suspicious_ips.add(client_ip)
            print(f"[SECURITY] Scraper detected: {client_ip} - {user_agent}")
            
            # Log to evidence ledger
            await self._log_to_evidence_ledger(
                "SCRAPER_DETECTED",
                {
                    "ip": client_ip,
                    "user_agent": user_agent,
                    "path": request.url.path,
                    "risk_level": "HIGH" if self._is_high_risk_scraper(user_agent) else "MEDIUM"
                },
                client_ip,
                user_agent
            )
            
            # Serve decoy data to high-risk scrapers
            if self._is_high_risk_scraper(user_agent):
                self.banned_ips.add(client_ip)
                await self._log_to_evidence_ledger(
                    "DECOY_SERVED",
                    {"ip": client_ip, "user_agent": user_agent},
                    client_ip,
                    user_agent
                )
                return self._serve_decoy_response()
        
        # Layer 4: Request pattern analysis
        if self._has_suspicious_pattern(request):
            await self._log_suspicious_activity(client_ip, request)
        
        # Layer 5: Record request for rate limiting
        self._record_request(client_ip)
        
        # Process legitimate request
        response = await call_next(request)
        
        # Add security headers
        response = self._add_security_headers(response)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP (handles proxies)."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host
    
    def _is_rate_limited(self, ip: str) -> bool:
        """Check if IP has exceeded rate limit."""
        if not self.redis:
            return False  # No Redis = no rate limiting
        
        key = f"rate_limit:{ip}"
        current = self.redis.get(key)
        
        if current and int(current) > 100:  # 100 requests per minute
            return True
        
        return False
    
    def _record_request(self, ip: str):
        """Record request for rate limiting."""
        if not self.redis:
            return
        
        key = f"rate_limit:{ip}"
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)  # 1 minute window
        pipe.execute()
    
    def _is_scraper(self, user_agent: str) -> bool:
        """Detect if User-Agent looks like a scraper."""
        return any(pattern in user_agent for pattern in self.scraper_patterns)
    
    def _is_high_risk_scraper(self, user_agent: str) -> bool:
        """Detect high-risk scraper (competitor bot)."""
        high_risk = ['scrapy', 'beautifulsoup', 'bot', 'crawler']
        return any(pattern in user_agent for pattern in high_risk)
    
    def _has_suspicious_pattern(self, request: Request) -> bool:
        """Detect suspicious request patterns."""
        client_ip = self._get_client_ip(request)
        
        # Suspicious: Rapid sequential provider ID enumeration
        if "/providers/" in request.url.path and request.method == "GET":
            if self._detect_id_enumeration(client_ip, "provider", request.url.path):
                return True
        
        # Suspicious: Accessing many shift endpoints rapidly
        if "/shifts/" in request.url.path and request.method == "GET":
            if self._detect_rapid_access(client_ip, "shifts"):
                return True
        
        return False
    
    def _detect_id_enumeration(self, ip: str, resource_type: str, path: str) -> bool:
        """
        Detect sequential ID enumeration attempts.
        
        Pattern: Accessing /providers/uuid1, /providers/uuid2, /providers/uuid3 rapidly
        """
        if not self.redis:
            return False
        
        key = f"enum_detect:{ip}:{resource_type}"
        
        # Store last 10 accessed paths
        self.redis.lpush(key, path)
        self.redis.ltrim(key, 0, 9)  # Keep only last 10
        self.redis.expire(key, 60)  # 1 minute window
        
        # If accessed 5+ different IDs in last minute, flag as enumeration
        accessed_paths = self.redis.lrange(key, 0, 9)
        if len(accessed_paths) >= 5:
            unique_ids = set(accessed_paths)
            if len(unique_ids) >= 5:
                return True
        
        return False
    
    def _detect_rapid_access(self, ip: str, resource_type: str) -> bool:
        """
        Detect rapid repeated access to same resource type.
        
        Pattern: Hitting /shifts/* endpoints 20+ times in 30 seconds
        """
        if not self.redis:
            return False
        
        key = f"rapid_access:{ip}:{resource_type}"
        current = self.redis.get(key)
        
        if current and int(current) > 20:  # 20 requests in 30 seconds
            return True
        
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 30)  # 30 second window
        pipe.execute()
        
        return False
    
    async def _is_whitelisted(self, ip: str) -> bool:
        """
        Check if IP is in whitelist (corporate networks).
        
        Whitelisted IPs bypass ALL security checks.
        """
        async with AsyncSessionLocal() as db:
            stmt = select(IPWhitelist).where(
                IPWhitelist.ip_address == ip,
                IPWhitelist.is_active == "1"
            )
            result = await db.execute(stmt)
            whitelist_entry = result.scalar_one_or_none()
            
            return whitelist_entry is not None
    
    async def _log_to_evidence_ledger(
        self,
        evidence_type: str,
        evidence_data: Dict,
        ip_address: str,
        user_agent: str
    ):
        """
        Log security violation to immutable Merkle-tree ledger.
        
        Creates court-ready, cryptographically provable evidence.
        """
        try:
            await log_security_violation(
                evidence_type=evidence_type,
                evidence_data=evidence_data,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            print(f"[SECURITY] Failed to log to evidence ledger: {e}")
    
    async def _log_suspicious_activity(self, ip: str, request: Request):
        """Log suspicious activity to evidence ledger."""
        print(f"[SECURITY] Suspicious activity from {ip}: {request.method} {request.url.path}")
        
        await self._log_to_evidence_ledger(
            "SUSPICIOUS_PATTERN",
            {
                "ip": ip,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params)
            },
            ip,
            request.headers.get("user-agent", "")
        )
    
    def _serve_decoy_response(self) -> JSONResponse:
        """
        Serve decoy/fake data to scrapers.
        
        Strategy: Return realistic-looking but completely fake data
        to waste scraper resources and poison their datasets.
        """
        decoy_data = {
            "shifts": [
                {
                    "id": "decoy-" + hashlib.md5(str(time.time()).encode()).hexdigest(),
                    "facility": "Decoy Facility " + str(i),
                    "rate": 99.99,  # Fake rate
                    "credential_type": "DECOY",
                    "status": "HONEYPOT"
                }
                for i in range(20)
            ],
            "_watermark": "VETTEDCARE_DECOY_RESPONSE"
        }
        
        return JSONResponse(
            status_code=200,
            content=decoy_data
        )
    
    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# Rate limiting decorator for specific endpoints
def rate_limit(max_calls: int = 10, period: int = 60):
    """
    Decorator for endpoint-specific rate limiting.
    
    Usage:
        @rate_limit(max_calls=10, period=60)  # 10 calls per minute
        async def my_endpoint():
            pass
    """
    def decorator(func):
        import functools
        from fastapi import Request, HTTPException, status
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request found, skip rate limiting
                return await func(*args, **kwargs)
            
            # Get client IP
            forwarded = request.headers.get("x-forwarded-for")
            client_ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
            
            # Check rate limit using Redis (if available)
            try:
                from app.database import get_redis_client
                redis = get_redis_client()
                
                if redis:
                    key = f"rate_limit:endpoint:{func.__name__}:{client_ip}"
                    current = redis.get(key)
                    
                    if current and int(current) >= max_calls:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Rate limit exceeded: {max_calls} calls per {period} seconds"
                        )
                    
                    pipe = redis.pipeline()
                    pipe.incr(key)
                    pipe.expire(key, period)
                    pipe.execute()
            except Exception as e:
                # Rate limiting failure shouldn't break the endpoint
                print(f"[RATE_LIMIT] Error: {e}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
