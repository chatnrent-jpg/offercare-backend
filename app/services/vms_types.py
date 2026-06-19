"""Shared VMS ingestion types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VmsShiftRecord:
    external_id: str
    facility_name: str
    shift_role: str
    hourly_pay_rate: float
    shift_starts_at: datetime
    source: str
