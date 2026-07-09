import time
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any, Set

# Inside-memory fast-pass cache maps to guarantee sub-millisecond Layer 0 security execution
VOLATILE_IP_WHITELIST_CACHE: Set[str] = {"127.0.0.1", "localhost", "10.0.1.10"}
VOLATILE_RATE_LIMIT_STORE: Dict[str, Dict[str, Any]] = {}

class HardenedFortressMiddleware(BaseHTTPMiddleware):
    """Enforces multi-layered IP whitelisting, bot interception, and microsecond caching rules."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # --- LAYER 0: MICROSECOND IP WHITELIST FAST-PASS ---
        if client_ip in VOLATILE_IP_WHITELIST_CACHE:
            return await call_next(request)
            
        # --- LAYER 1: FAST CORRUPTED USER-AGENT ANALYSIS ---
        user_agent = request.headers.get("user-agent", "").lower()
        bot_signatures = ["scrapy", "python-requests", "curl", "headlesschromium", "selenium"]
        
        if any(sig in user_agent for sig in bot_signatures):
            return Response(
                content='{"status": "success", "data": [{"id": 9999, "rate": 10.00, "role": "DECOY_NODE"}]}',
                media_type="application/json",
                status_code=status.HTTP_200_OK
            )
            
        # --- LAYER 2: HIGH-SPEED IN-MEMORY RATE LIMITING ---
        ip_metrics = VOLATILE_RATE_LIMIT_STORE.get(client_ip, {"count": 0, "window_start": current_time})
        
        if current_time - ip_metrics["window_start"] > 60:
            ip_metrics = {"count": 1, "window_start": current_time}
        else:
            ip_metrics["count"] += 1
            
        VOLATILE_RATE_LIMIT_STORE[client_ip] = ip_metrics
        
        if ip_metrics["count"] > 100:
            return Response(
                content='{"detail": "Too many requests. Rate limit boundary breached."}',
                media_type="application/json",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS
            )
            
        return await call_next(request)
