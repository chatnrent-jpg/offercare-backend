"""Batch scrape Pennsylvania, Delaware, and New Jersey hospital facilities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas import FacilityScrapeResponse
from app.services.de_facility_scraper import scrape_and_ingest_delaware_hospitals
from app.services.nj_facility_scraper import scrape_and_ingest_new_jersey_hospitals
from app.services.pa_facility_scraper import scrape_and_ingest_pennsylvania_hospitals


@dataclass(frozen=True)
class ExpansionScrapeResult:
    pennsylvania: FacilityScrapeResponse
    delaware: FacilityScrapeResponse
    new_jersey: FacilityScrapeResponse

    @property
    def fetched(self) -> int:
        return self.pennsylvania.fetched + self.delaware.fetched + self.new_jersey.fetched

    @property
    def created(self) -> int:
        return self.pennsylvania.created + self.delaware.created + self.new_jersey.created

    @property
    def updated(self) -> int:
        return self.pennsylvania.updated + self.delaware.updated + self.new_jersey.updated

    @property
    def skipped(self) -> int:
        return self.pennsylvania.skipped + self.delaware.skipped + self.new_jersey.skipped

    @property
    def errors(self) -> list[str]:
        return [*self.pennsylvania.errors, *self.delaware.errors, *self.new_jersey.errors]


def scrape_and_ingest_expansion_states(
    db: Session,
    *,
    limit: int | None = None,
    county: str | None = None,
) -> ExpansionScrapeResult:
    pa_result = scrape_and_ingest_pennsylvania_hospitals(db, limit=limit, county=county)
    de_result = scrape_and_ingest_delaware_hospitals(db, limit=limit, county=county)
    nj_result = scrape_and_ingest_new_jersey_hospitals(db, limit=limit, county=county)
    return ExpansionScrapeResult(
        pennsylvania=pa_result,
        delaware=de_result,
        new_jersey=nj_result,
    )
