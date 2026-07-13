"""Run Alembic migrations for VettedMe.ai."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import settings
from app.database import engine as default_engine

ROOT = Path(__file__).resolve().parents[1]
_LEGACY_STAMP_REVISION = "019_instant_pay_tables"


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    url = settings.DATABASE_URL.replace("%", "%%")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _current_alembic_revision(engine: Engine) -> str | None:
    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
    if row is None:
        return None
    return str(row[0])


def run_migrations(engine: Engine | None = None) -> None:
    db_engine = engine or default_engine
    inspector = inspect(db_engine)
    has_core = inspector.has_table("maryland_providers")
    version_num = _current_alembic_revision(db_engine)

    cfg = _alembic_config()
    if has_core and not version_num:
        # Legacy DB: tables exist but alembic_version is missing or empty — stamp baseline, then upgrade.
        command.stamp(cfg, _LEGACY_STAMP_REVISION)
    command.upgrade(cfg, "head")
