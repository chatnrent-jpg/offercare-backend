"""Batch scrape nursing homes and home health agencies across Mid-Atlantic states."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas import FacilityScrapeResponse
from app.services.cms_post_acute_scraper import (
    scrape_and_ingest_home_health_agencies,
    scrape_and_ingest_nursing_homes,
)
from app.services.states import supported_states


@dataclass(frozen=True)
class PostAcuteExpansionResult:
    nursing_homes: FacilityScrapeResponse
    home_health: FacilityScrapeResponse

    @property
    def fetched(self) -> int:
        return self.nursing_homes.fetched + self.home_health.fetched

    @property
    def created(self) -> int:
        return self.nursing_homes.created + self.home_health.created

    @property
    def updated(self) -> int:
        return self.nursing_homes.updated + self.home_health.updated

    @property
    def skipped(self) -> int:
        return self.nursing_homes.skipped + self.home_health.skipped

    @property
    def errors(self) -> list[str]:
        return [*self.nursing_homes.errors, *self.home_health.errors]

    @property
    def shifts_created(self) -> int:
        return self.nursing_homes.shifts_created + self.home_health.shifts_created

    @property
    def shifts_facilities_processed(self) -> int:
        return (
            self.nursing_homes.shifts_facilities_processed
            + self.home_health.shifts_facilities_processed
        )

    @property
    def matched_push_alerts_sent(self) -> int:
        return (
            self.nursing_homes.matched_push_alerts_sent
            + self.home_health.matched_push_alerts_sent
        )


def _merge_responses(responses: list[FacilityScrapeResponse], *, source: str) -> FacilityScrapeResponse:
    return FacilityScrapeResponse(
        source=source,
        state="MID_ATLANTIC",
        fetched=sum(row.fetched for row in responses),
        created=sum(row.created for row in responses),
        updated=sum(row.updated for row in responses),
        skipped=sum(row.skipped for row in responses),
        errors=[error for row in responses for error in row.errors],
        shifts_facilities_processed=sum(row.shifts_facilities_processed for row in responses),
        shifts_created=sum(row.shifts_created for row in responses),
        matched_push_alerts_sent=sum(row.matched_push_alerts_sent for row in responses),
    )


def scrape_and_ingest_post_acute_mid_atlantic(
    db: Session,
    *,
    limit: int | None = None,
    county: str | None = None,
    auto_create_shifts: bool = False,
) -> PostAcuteExpansionResult:
    states = supported_states()
    nursing_home_results = [
        scrape_and_ingest_nursing_homes(
            db,
            state,
            limit=limit,
            county=county,
            auto_create_shifts=auto_create_shifts,
        )
        for state in states
    ]
    home_health_results = [
        scrape_and_ingest_home_health_agencies(
            db,
            state,
            limit=limit,
            county=county,
            auto_create_shifts=auto_create_shifts,
        )
        for state in states
    ]
    from app.services.cms_post_acute_scraper import CMS_HOME_HEALTH_SOURCE, CMS_NURSING_HOME_SOURCE

    return PostAcuteExpansionResult(
        nursing_homes=_merge_responses(nursing_home_results, source=CMS_NURSING_HOME_SOURCE),
        home_health=_merge_responses(home_health_results, source=CMS_HOME_HEALTH_SOURCE),
    )
