from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.config import settings
from app.database import engine
from app.migrations import _alembic_config, run_migrations

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_artifacts_exist() -> None:
    assert (ROOT / "alembic.ini").is_file()
    assert (ROOT / "alembic" / "env.py").is_file()
    assert (ROOT / "alembic" / "versions" / "001_initial_schema.py").is_file()
    assert (ROOT / "alembic" / "versions" / "002_multistate_columns.py").is_file()
    assert (ROOT / "alembic" / "versions" / "003_shift_schedule_columns.py").is_file()
    assert (ROOT / "alembic" / "versions" / "004_push_subscriptions.py").is_file()


def test_run_migrations_stamps_existing_database() -> None:
    inspector = inspect(engine)
    assert inspector.has_table("maryland_providers")

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM alembic_version"))
        conn.commit()

    run_migrations(engine)
    assert inspector.has_table("alembic_version")


def test_alembic_upgrade_head_on_configured_database() -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    assert inspector.has_table("ops_audit_log")
    assert inspector.has_table("alembic_version")


def test_docker_entrypoint_runs_migrations() -> None:
    text = (ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "alembic upgrade head" in text


def test_env_example_documents_migrations() -> None:
    assert "DATABASE_URL" in (ROOT / ".env.example").read_text(encoding="utf-8")
