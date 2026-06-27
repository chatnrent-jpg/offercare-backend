"""Unified shift matcher — one code path for staging JSON and PostgreSQL."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from strategy.db_workforce_adapter import candidates_from_registry, load_db_candidates
from strategy.shift_match_core import rank_compliant_matches


class UnifiedShiftMatcher:
    """Single matcher surface for desk orchestrator, ops console, and shift ingest."""

    def __init__(
        self,
        candidates: list[dict[str, Any]],
        *,
        source: str = "registry",
    ) -> None:
        if not isinstance(candidates, list):
            raise TypeError("candidates must be a list")
        self.candidates = list(candidates)
        self.source = source

    @classmethod
    def from_registry(cls, workforce_registry: dict[str, Any]) -> UnifiedShiftMatcher:
        return cls(candidates_from_registry(workforce_registry), source="registry")

    @classmethod
    def from_database(
        cls,
        db: Session,
        *,
        facility_id: UUID | None = None,
    ) -> UnifiedShiftMatcher:
        return cls(load_db_candidates(db, facility_id=facility_id), source="postgresql")

    def find_compliant_matches(
        self,
        shift_request: dict[str, Any],
        evaluation_timestamp: str,
    ) -> list[dict[str, Any]]:
        matches = rank_compliant_matches(self.candidates, shift_request, evaluation_timestamp)
        for row in matches:
            meta = row.setdefault("_match_meta", {})
            meta["matcher_source"] = self.source
        return matches
