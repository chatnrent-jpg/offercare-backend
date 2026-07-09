"""
Modern Async SQLAlchemy 2.0 Database Configuration

Elite Database Engineer Migration — 2026-07-06
Zero synchronous patterns. Full async/await. Type-annotated ORM.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, declarative_base, sessionmaker

from app.config import settings

# ============================================================================
# ASYNC ENGINE — Production Async PostgreSQL Connection
# ============================================================================

# Create async engine for all async operations
# Auto-convert DATABASE_URL to async format if ASYNC_DATABASE_URL not set
_async_db_url = settings.ASYNC_DATABASE_URL or settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

async_engine: AsyncEngine = create_async_engine(
    _async_db_url,  # postgresql+asyncpg://...
    echo=False,  # Set to True for SQL query logging
    pool_size=20,  # Connection pool size
    max_overflow=10,  # Additional connections beyond pool_size
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autocommit=False,
    autoflush=False,
)


# ============================================================================
# DECLARATIVE BASE — SQLAlchemy 2.0 Type-Annotated ORM
# ============================================================================

class Base(DeclarativeBase):
    """
    Modern SQLAlchemy 2.0 declarative base with type annotations.
    
    All models inherit from this base and use:
    - Mapped[...] type annotations
    - mapped_column() for columns
    - Relationship() for foreign keys
    """
    
    # Custom metadata with naming conventions for constraints
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# ============================================================================
# ASYNC SESSION MANAGEMENT
# ============================================================================

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session dependency for FastAPI routes.
    
    Usage:
        @app.get("/api/example")
        async def example_route(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Model))
            return result.scalars().all()
    
    Yields:
        AsyncSession: Active database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for manual session management.
    
    Usage:
        async with async_session_scope() as session:
            result = await session.execute(select(Model))
            await session.commit()
    
    Yields:
        AsyncSession: Active database session with auto-commit/rollback
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database schema by creating all tables.
    
    Should be called on application startup.
    """
    async with async_engine.begin() as conn:
        # Import all models to register them with Base.metadata
        from app import models  # noqa: F401
        
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """
    Drop all tables (DANGEROUS — use only in development/testing).
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ============================================================================
# LEGACY SYNC SUPPORT (Deprecated — migrate to async)
# ============================================================================

# Legacy synchronous engine for gradual migration
# TODO: Remove once all code migrated to async
sync_engine = create_engine(
    settings.DATABASE_URL,  # postgresql://...
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

# Aliases for backward compatibility with legacy test code
SessionLocal = SyncSessionLocal  # Alias for legacy tests
engine = sync_engine  # Alias for legacy tests

# Legacy declarative base for backward compatibility
LegacyBase = declarative_base()


def get_sync_db():
    """
    Legacy synchronous database session (DEPRECATED).
    
    ⚠️ WARNING: This is deprecated. Migrate to get_async_db().
    """
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Alias for backward compatibility with legacy code
get_db = get_sync_db
