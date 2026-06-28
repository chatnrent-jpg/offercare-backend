"""Clinician calendar events — persistent provider time vault for shift and availability blocks."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base

EVENT_TYPE_SHIFT_COMMITMENT = "SHIFT_COMMITMENT"
EVENT_TYPE_SOFT_BLOCK_PREFERENCE = "SOFT_BLOCK_PREFERENCE"
EVENT_TYPE_BLACKOUT_UNAVAILABLE = "BLACKOUT_UNAVAILABLE"

CALENDAR_EVENT_TYPES = (
    EVENT_TYPE_SHIFT_COMMITMENT,
    EVENT_TYPE_SOFT_BLOCK_PREFERENCE,
    EVENT_TYPE_BLACKOUT_UNAVAILABLE,
)


class ClinicianCalendarEvent(Base):
    """Time vault row — locked shifts, soft preferences, and blackout unavailability."""

    __tablename__ = "clinician_calendar_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(String(128), nullable=False, index=True)
    shift_id = Column(String(128), nullable=True, index=True)
    event_type = Column(String(64), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    metadata_json = Column(Text, nullable=True)


# Alias for directive naming compatibility.
ClinicianCalendarEventModel = ClinicianCalendarEvent


if __name__ == "__main__":
    print("COMPILE_OK clinician_calendar")
    print(f"table={ClinicianCalendarEvent.__tablename__}")
    print(f"event_types={list(CALENDAR_EVENT_TYPES)}")
