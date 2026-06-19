"""PostGIS geography columns and GiST indexes for native radius matching."""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

revision: str = "011_postgis_geo"
down_revision: Union[str, None] = "010_outreach_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _postgis_available(bind) -> bool:
    bind.execute(text("SAVEPOINT offercare_postgis_probe"))
    try:
        bind.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        version = bind.execute(text("SELECT PostGIS_Version()")).scalar()
        bind.execute(text("RELEASE SAVEPOINT offercare_postgis_probe"))
        return bool(version)
    except Exception:
        bind.execute(text("ROLLBACK TO SAVEPOINT offercare_postgis_probe"))
        return False


def _sync_trigger_sql(table: str) -> None:
    fn_name = f"sync_{table}_location_geog"
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {fn_name}()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
            NEW.location_geog := ST_SetSRID(
              ST_MakePoint(NEW.longitude::double precision, NEW.latitude::double precision),
              4326
            )::geography;
          ELSE
            NEW.location_geog := NULL;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(f"DROP TRIGGER IF EXISTS trg_sync_{table}_location_geog ON {table}")
    op.execute(
        f"""
        CREATE TRIGGER trg_sync_{table}_location_geog
        BEFORE INSERT OR UPDATE OF latitude, longitude ON {table}
        FOR EACH ROW EXECUTE PROCEDURE {fn_name}();
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _postgis_available(bind):
        return

    inspector = inspect(bind)
    for table in ("maryland_facilities", "maryland_providers"):
        if table not in inspector.get_table_names():
            continue
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "location_geog" not in columns:
            op.execute(f"ALTER TABLE {table} ADD COLUMN location_geog geography(POINT, 4326)")

        op.execute(
            f"""
            UPDATE {table}
            SET location_geog = ST_SetSRID(
                ST_MakePoint(longitude::double precision, latitude::double precision),
                4326
            )::geography
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND location_geog IS NULL
            """
        )
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS ix_{table}_location_geog
            ON {table} USING GIST (location_geog)
            """
        )
        _sync_trigger_sql(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table in ("maryland_providers", "maryland_facilities"):
        if table not in inspector.get_table_names():
            continue
        op.execute(f"DROP TRIGGER IF EXISTS trg_sync_{table}_location_geog ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS sync_{table}_location_geog()")
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "location_geog" in columns:
            op.execute(f"DROP INDEX IF EXISTS ix_{table}_location_geog")
            op.drop_column(table, "location_geog")
