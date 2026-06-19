"""Backward-compatible alias — use app.migrations.run_migrations instead."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.migrations import run_migrations


def apply_schema_patches(engine: Engine) -> None:
    run_migrations(engine)
