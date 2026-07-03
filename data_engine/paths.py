"""Filesystem layout for Manus handoff → Cursor processing."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ENGINE_ROOT = REPO_ROOT / "data_engine"

RAW_LEADS_DIR = DATA_ENGINE_ROOT / "raw_leads"
LEADS_DIR = REPO_ROOT / "leads"
INCOMING_CONTRACTS_DIR = DATA_ENGINE_ROOT / "incoming_contracts"
INCOMING_SHIFTS_DIR = DATA_ENGINE_ROOT / "incoming_shifts"
PROCESSED_DIR = DATA_ENGINE_ROOT / "processed"
MIGRATIONS_DIR = DATA_ENGINE_ROOT / "migrations"


def ensure_data_engine_dirs() -> None:
    for path in (
        RAW_LEADS_DIR,
        LEADS_DIR,
        INCOMING_CONTRACTS_DIR,
        INCOMING_SHIFTS_DIR,
        PROCESSED_DIR,
        MIGRATIONS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
