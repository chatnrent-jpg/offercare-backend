"""PostGIS helpers for indexed radius matching (falls back to Haversine in geo_matching)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings

METERS_PER_MILE = 1609.344


def miles_to_meters(miles: float) -> float:
    return float(miles) * METERS_PER_MILE


@lru_cache(maxsize=4)
def _postgis_extension_available(engine_url: str) -> bool:
    from app.database import engine

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
        return bool(version)
    except Exception:
        return False


@lru_cache(maxsize=4)
def _postgis_columns_present(engine_url: str) -> bool:
    from app.database import engine

    try:
        inspector = inspect(engine)
        if not inspector.has_table("maryland_providers"):
            return False
        columns = {col["name"] for col in inspector.get_columns("maryland_providers")}
        return "location_geog" in columns
    except Exception:
        return False


def clear_postgis_cache() -> None:
    _postgis_extension_available.cache_clear()
    _postgis_columns_present.cache_clear()


def postgis_geo_ready(db: Session | None = None) -> bool:
    if not settings.GEO_MATCH_USE_POSTGIS:
        return False
    from app.database import engine

    url = str(engine.url)
    if not _postgis_extension_available(url):
        return False
    return _postgis_columns_present(url)


def query_provider_geo_candidates(
    db: Session,
    *,
    facility_longitude: float,
    facility_latitude: float,
    state: str,
    radius_miles: float,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return providers in state within radius (or without geocoded location)."""
    radius_meters = miles_to_meters(radius_miles)
    rows = db.execute(
        text(
            """
            SELECT
                p.provider_id,
                p.full_name,
                p.credential_type,
                p.dispatch_status,
                p.min_hourly_rate,
                p.service_lines,
                p.license_status,
                p.state,
                CASE
                    WHEN p.location_geog IS NULL THEN NULL
                    ELSE ST_Distance(
                        p.location_geog,
                        ST_SetSRID(ST_MakePoint(:facility_lon, :facility_lat), 4326)::geography
                    ) / :meters_per_mile
                END AS distance_miles
            FROM maryland_providers p
            WHERE p.state = :state
              AND (
                p.location_geog IS NULL
                OR ST_DWithin(
                    p.location_geog,
                    ST_SetSRID(ST_MakePoint(:facility_lon, :facility_lat), 4326)::geography,
                    :radius_meters
                )
              )
            ORDER BY distance_miles NULLS LAST, p.full_name
            LIMIT :limit
            """
        ),
        {
            "facility_lon": facility_longitude,
            "facility_lat": facility_latitude,
            "state": state,
            "radius_meters": radius_meters,
            "meters_per_mile": METERS_PER_MILE,
            "limit": limit,
        },
    ).mappings()
    return [dict(row) for row in rows]


def query_geo_eligible_provider_ids(
    db: Session,
    *,
    facility_longitude: float,
    facility_latitude: float,
    state: str,
    radius_miles: float,
) -> set[UUID]:
    radius_meters = miles_to_meters(radius_miles)
    rows = db.execute(
        text(
            """
            SELECT p.provider_id
            FROM maryland_providers p
            WHERE p.state = :state
              AND (
                p.location_geog IS NULL
                OR ST_DWithin(
                    p.location_geog,
                    ST_SetSRID(ST_MakePoint(:facility_lon, :facility_lat), 4326)::geography,
                    :radius_meters
                )
              )
            """
        ),
        {
            "facility_lon": facility_longitude,
            "facility_lat": facility_latitude,
            "state": state,
            "radius_meters": radius_meters,
        },
    ).scalars()
    return set(rows)


def describe_postgis_status(db: Session) -> dict[str, Any]:
    extension = False
    version: str | None = None
    columns = False
    gist_indexes = False
    try:
        version = db.execute(text("SELECT PostGIS_Version()")).scalar()
        extension = bool(version)
    except Exception:
        db.rollback()
        extension = False

    if extension:
        try:
            inspector = inspect(db.get_bind())
            columns = "location_geog" in {
                col["name"] for col in inspector.get_columns("maryland_providers")
            }
            indexes = {idx["name"] for idx in inspector.get_indexes("maryland_providers")}
            gist_indexes = "ix_maryland_providers_location_geog" in indexes
        except Exception:
            db.rollback()
            columns = False

    ready = extension and columns and settings.GEO_MATCH_USE_POSTGIS
    return {
        "postgis_enabled": ready,
        "postgis_version": version,
        "postgis_columns_ready": columns,
        "postgis_gist_index_ready": gist_indexes,
        "geo_match_use_postgis": settings.GEO_MATCH_USE_POSTGIS,
    }
