"""Run Alembic migrations for VettedCare.ai."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.config import settings
from app.database import engine as default_engine

ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    url = settings.DATABASE_URL.replace("%", "%%")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def run_migrations(engine: Engine | None = None) -> None:
    db_engine = engine or default_engine
    inspector = inspect(db_engine)
    has_version = inspector.has_table("alembic_version")
    has_core = inspector.has_table("maryland_providers")

    cfg = _alembic_config()
    if has_core and not has_version:
        command.stamp(cfg, "head")
        return
    command.upgrade(cfg, "head")
