"""In-memory sliding-window rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

_WINDOW_SECONDS = 60


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, *, window_seconds: int = _WINDOW_SECONDS) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        queue = self._hits[key]
        while queue and now - queue[0] > window_seconds:
            queue.popleft()
        if len(queue) >= limit:
            return False
        queue.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


rate_limiter = SlidingWindowRateLimiter()


def reset_rate_limiter() -> None:
    rate_limiter.reset()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _limit_for_path(path: str) -> tuple[str, int] | None:
    if path == "/api/clinicians/login":
        return "login", settings.RATE_LIMIT_LOGIN_PER_MINUTE
    if path == "/api/clinicians/apply":
        return "apply", settings.RATE_LIMIT_APPLY_PER_MINUTE
    if path == "/shift-sniper/twilio/sms":
        return "twilio", settings.RATE_LIMIT_TWILIO_PER_MINUTE
    if path.startswith("/api/") or path.startswith("/shift-sniper/"):
        return "api", settings.RATE_LIMIT_DEFAULT_PER_MINUTE
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        bucket = _limit_for_path(request.url.path)
        if bucket is None:
            return await call_next(request)

        bucket_name, limit = bucket
        key = f"{bucket_name}:{_client_ip(request)}"
        if not rate_limiter.allow(key, limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "rate_limit_exceeded", "bucket": bucket_name},
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )
        return await call_next(request)
