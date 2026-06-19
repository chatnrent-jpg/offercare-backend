"""Runtime ASGI app handle for in-process live scraper HTTP calls."""

from __future__ import annotations

from typing import Any

asgi_app: Any | None = None


def register_asgi_app(app: Any) -> None:
    global asgi_app
    asgi_app = app
