"""Application logging configuration."""

from __future__ import annotations

import logging

from app.config import settings


def configure_logging() -> None:
    level = getattr(logging, str(settings.LOG_LEVEL).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
    logging.getLogger("uvicorn.access").setLevel(level)
