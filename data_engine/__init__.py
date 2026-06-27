"""VettedCare B2B recruitment & contract data engine (Cursor-local parsing + matching)."""

from data_engine.paths import (
    INCOMING_CONTRACTS_DIR,
    INCOMING_SHIFTS_DIR,
    RAW_LEADS_DIR,
    ensure_data_engine_dirs,
)

__all__ = [
    "RAW_LEADS_DIR",
    "INCOMING_CONTRACTS_DIR",
    "INCOMING_SHIFTS_DIR",
    "ensure_data_engine_dirs",
]
