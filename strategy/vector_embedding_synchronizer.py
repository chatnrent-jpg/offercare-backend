"""Autonomous vector embedding synchronizer — pgvector maintenance worker."""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_EMBEDDING_DIMENSIONS = 1536
_EMBEDDING_SOURCE_LIVE = "live_llm"
_EMBEDDING_SOURCE_HASH = "hash_fallback"


class VectorEmbeddingSynchronizerHardStop(RuntimeError):
    """Hive halt — vector embedding synchronizer import or DB failure."""


@dataclass(frozen=True)
class StaleProviderProfile:
    provider_id: str
    profile_text: str
    profile_modified_at: datetime
    embeddings_last_updated_at: datetime | None


@dataclass(frozen=True)
class GeneratedProviderEmbedding:
    provider_id: str
    profile_text: str
    vector: tuple[float, ...]
    embedding_source: str
    embedding_dimensions: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _embedding_dimensions() -> int:
    try:
        from app.config import settings

        return int(settings.SEMANTIC_EMBEDDING_DIMENSIONS or _DEFAULT_EMBEDDING_DIMENSIONS)
    except Exception:  # noqa: BLE001
        return _DEFAULT_EMBEDDING_DIMENSIONS


def _embedding_model_name() -> str:
    try:
        from app.config import settings

        return str(settings.SEMANTIC_EMBEDDING_MODEL or "text-embedding-3-small")
    except Exception:  # noqa: BLE001
        return "text-embedding-3-small"


def _llm_embedding_configured() -> bool:
    try:
        from app.config import settings

        return bool(str(settings.OUTREACH_LLM_API_KEY or "").strip()) and bool(
            str(settings.OUTREACH_LLM_URL or "").strip()
        )
    except Exception:  # noqa: BLE001
        return False


def _hash_embed_text(text: str, *, dimensions: int) -> list[float]:
    """Deterministic, lookahead-safe hash embedding for offline fallback."""
    seed = hashlib.sha256(str(text or "").strip().lower().encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
        for byte in block:
            values.append((byte / 127.5) - 1.0)
            if len(values) >= dimensions:
                break
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _build_provider_profile_text(db: Session, provider: Any) -> str:
    try:
        from api.vector_match_engine import _build_provider_profile_text as build_text

        return build_text(db, provider)
    except ImportError:
        pass
    try:
        from app.models import MdProviderCompliance

        compliance = (
            db.query(MdProviderCompliance)
            .filter(MdProviderCompliance.provider_id == provider.provider_id)
            .first()
        )
    except Exception:  # noqa: BLE001
        compliance = None
    county = compliance.home_county if compliance else None
    gna = bool(compliance.has_gna_endorsement) if compliance else False
    parts = [
        f"Name: {provider.full_name}",
        f"Role: {provider.credential_type}",
        f"Service lines: {provider.service_lines}",
        f"County: {county or provider.home_zip or 'Maryland'}",
        f"License status: {provider.license_status}",
        f"Vetted status: {provider.vetted_status}",
        f"GNA endorsement: {gna}",
        f"Min hourly rate: {provider.min_hourly_rate}",
        f"Notes: {provider.verification_notes or ''}",
    ]
    return " | ".join(part for part in parts if part)


def _profile_modified_at(provider: Any) -> datetime:
    candidates = [
        _utc(getattr(provider, "vetted_status_updated_at", None)),
        _utc(getattr(provider, "last_verified_timestamp", None)),
        _utc(getattr(provider, "applied_at", None)),
    ]
    resolved = [value for value in candidates if value is not None]
    if resolved:
        return max(resolved)
    return _utc_now()


class VectorEmbeddingSynchronizer:
    """Cron-ready worker — scan, generate, and upsert provider profile embeddings."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._owns_session = False
        self.embedding_dimensions = _embedding_dimensions()
        self.embedding_model = _embedding_model_name()

    @property
    def db(self) -> Session:
        if self._db is None:
            try:
                from app.database import SessionLocal
            except Exception as exc:  # noqa: BLE001
                raise VectorEmbeddingSynchronizerHardStop("database_session_import_failed") from exc
            self._db = SessionLocal()
            self._owns_session = True
        return self._db

    def close(self) -> None:
        if self._owns_session and self._db is not None:
            self._db.close()
            self._db = None
            self._owns_session = False

    def _pgvector_ready(self) -> bool:
        try:
            row = self.db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1")
            ).first()
            return row is not None
        except SQLAlchemyError:
            return False

    def scan_stale_profiles(self, *, limit: int = 500) -> list[StaleProviderProfile]:
        """Find providers missing embeddings or with stale vector metadata."""
        try:
            from app.models import MarylandProvider
        except ImportError as exc:
            raise VectorEmbeddingSynchronizerHardStop("maryland_provider_import_failed") from exc

        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT
                        p.provider_id,
                        e.updated_at AS embeddings_last_updated_at
                    FROM maryland_providers p
                    LEFT JOIN provider_profile_embeddings e
                        ON e.provider_id = p.provider_id
                    WHERE
                        e.provider_id IS NULL
                        OR e.embedding IS NULL
                        OR e.updated_at IS NULL
                        OR e.updated_at < COALESCE(
                            p.vetted_status_updated_at,
                            p.last_verified_timestamp,
                            p.applied_at,
                            NOW()
                        )
                    ORDER BY COALESCE(e.updated_at, p.applied_at) ASC NULLS FIRST
                    LIMIT :limit
                    """
                ),
                {"limit": int(limit)},
            ).mappings().all()
        except SQLAlchemyError as exc:
            raise VectorEmbeddingSynchronizerHardStop("stale_profile_scan_failed") from exc

        stale: list[StaleProviderProfile] = []
        for row in rows:
            provider_uuid = row["provider_id"]
            provider = (
                self.db.query(MarylandProvider)
                .filter(MarylandProvider.provider_id == provider_uuid)
                .first()
            )
            if provider is None:
                continue
            profile_text = _build_provider_profile_text(self.db, provider)
            stale.append(
                StaleProviderProfile(
                    provider_id=str(provider.provider_id),
                    profile_text=profile_text,
                    profile_modified_at=_profile_modified_at(provider),
                    embeddings_last_updated_at=_utc(row.get("embeddings_last_updated_at")),
                )
            )
        return stale

    def _live_embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        if not texts or not _llm_embedding_configured():
            return None
        try:
            from app.config import settings
        except Exception:  # noqa: BLE001
            return None

        url = str(settings.OUTREACH_LLM_URL or "").rstrip("/")
        if not url.endswith("/embeddings"):
            embed_url = f"{url}/embeddings" if url.endswith("/v1") else f"{url.rstrip('/')}/v1/embeddings"
        else:
            embed_url = url

        headers = {
            "Authorization": f"Bearer {settings.OUTREACH_LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.embedding_model,
            "input": texts,
        }
        try:
            with httpx.Client(timeout=float(settings.OUTREACH_LLM_TIMEOUT_SECONDS)) as client:
                response = client.post(embed_url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            logger.warning("HIVE_VECTOR_SYNC: live embedding API failed error=%s", exc)
            return None

        rows = payload.get("data") or []
        if len(rows) != len(texts):
            logger.warning("HIVE_VECTOR_SYNC: live embedding response size mismatch")
            return None

        vectors: list[list[float]] = []
        for row in sorted(rows, key=lambda item: int(item.get("index", 0))):
            embedding = row.get("embedding")
            if not isinstance(embedding, list):
                return None
            if len(embedding) != self.embedding_dimensions:
                return None
            vectors.append([float(value) for value in embedding])
        return vectors

    def generate_provider_embeddings(
        self,
        stale_profiles: list[StaleProviderProfile],
    ) -> list[GeneratedProviderEmbedding]:
        """Generate dense vectors for stale profiles — live LLM with hash fallback."""
        if not stale_profiles:
            return []

        texts = [row.profile_text for row in stale_profiles]
        live_vectors = self._live_embed_texts(texts)
        use_live = live_vectors is not None and len(live_vectors) == len(stale_profiles)

        generated: list[GeneratedProviderEmbedding] = []
        for index, profile in enumerate(stale_profiles):
            if use_live and live_vectors is not None:
                vector = live_vectors[index]
                source = _EMBEDDING_SOURCE_LIVE
            else:
                vector = _hash_embed_text(profile.profile_text, dimensions=self.embedding_dimensions)
                source = _EMBEDDING_SOURCE_HASH

            generated.append(
                GeneratedProviderEmbedding(
                    provider_id=profile.provider_id,
                    profile_text=profile.profile_text,
                    vector=tuple(vector),
                    embedding_source=source,
                    embedding_dimensions=self.embedding_dimensions,
                )
            )

        if not use_live:
            logger.warning(
                "HIVE_VECTOR_SYNC: using hash fallback for %s profile(s)",
                len(generated),
            )
        return generated

    def commit_vector_sync(
        self,
        embeddings: list[GeneratedProviderEmbedding],
    ) -> dict[str, Any]:
        """Upsert embedding vectors inside a single database transaction."""
        if not embeddings:
            return {
                "ok": True,
                "committed": 0,
                "embedding_model": self.embedding_model,
                "pgvector_ready": self._pgvector_ready(),
            }

        if not self._pgvector_ready():
            logger.warning("HIVE_VECTOR_SYNC: pgvector extension unavailable — commit skipped")
            return {
                "ok": False,
                "committed": 0,
                "embedding_model": self.embedding_model,
                "pgvector_ready": False,
                "message": "pgvector_not_enabled",
            }

        synced_at = _utc_now()
        committed = 0
        try:
            with self.db.begin():
                for row in embeddings:
                    literal = _vector_literal(list(row.vector))
                    self.db.execute(
                        text(
                            """
                            INSERT INTO provider_profile_embeddings (
                                provider_id,
                                profile_text,
                                embedding,
                                updated_at
                            )
                            VALUES (
                                :provider_id,
                                :profile_text,
                                CAST(:embedding AS vector),
                                :updated_at
                            )
                            ON CONFLICT (provider_id) DO UPDATE SET
                                profile_text = EXCLUDED.profile_text,
                                embedding = EXCLUDED.embedding,
                                updated_at = EXCLUDED.updated_at
                            """
                        ),
                        {
                            "provider_id": row.provider_id,
                            "profile_text": row.profile_text,
                            "embedding": literal,
                            "updated_at": synced_at,
                        },
                    )
                    committed += 1
        except SQLAlchemyError as exc:
            logger.warning("HIVE_VECTOR_SYNC: commit failed error=%s", exc)
            return {
                "ok": False,
                "committed": 0,
                "embedding_model": self.embedding_model,
                "pgvector_ready": True,
                "message": str(exc),
            }

        return {
            "ok": True,
            "committed": committed,
            "embedding_model": self.embedding_model,
            "pgvector_ready": True,
            "embeddings_last_updated_at": synced_at.isoformat(),
        }

    def run_sync_cycle(self, *, limit: int = 500) -> dict[str, Any]:
        """Scan stale profiles, generate vectors, and commit in one maintenance pass."""
        stale = self.scan_stale_profiles(limit=limit)
        generated = self.generate_provider_embeddings(stale)
        commit_result = self.commit_vector_sync(generated)
        live_count = sum(1 for row in generated if row.embedding_source == _EMBEDDING_SOURCE_LIVE)
        fallback_count = sum(1 for row in generated if row.embedding_source == _EMBEDDING_SOURCE_HASH)
        return {
            "ok": bool(commit_result.get("ok")),
            "scanned_stale": len(stale),
            "generated": len(generated),
            "live_embeddings": live_count,
            "fallback_embeddings": fallback_count,
            **commit_result,
        }


if __name__ == "__main__":
    print("COMPILE_OK vector_embedding_synchronizer")
    synchronizer = VectorEmbeddingSynchronizer(db=None)
    sample_text = "CNA GNA Montgomery SNF dementia care night shift verified compliant"
    hash_vector = _hash_embed_text(sample_text, dimensions=synchronizer.embedding_dimensions)
    norm = math.sqrt(sum(value * value for value in hash_vector))
    stale_sample = [
        StaleProviderProfile(
            provider_id="00000000-0000-0000-0000-000000000001",
            profile_text=sample_text,
            profile_modified_at=_utc_now(),
            embeddings_last_updated_at=None,
        )
    ]
    generated = synchronizer.generate_provider_embeddings(stale_sample)
    print(f"engine={synchronizer.__class__.__name__}")
    print(f"dimensions={synchronizer.embedding_dimensions}")
    print(f"hash_norm={round(norm, 6)}")
    print(f"generated_source={generated[0].embedding_source if generated else 'none'}")
