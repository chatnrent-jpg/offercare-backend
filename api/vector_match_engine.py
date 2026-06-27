"""Semantic shift matching — pgvector cosine similarity over provider profile embeddings."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.config import settings
from app.database import get_db
from app.models import MdProviderCompliance, MarylandProvider
from app.services.vetted_status import VETTED_CLEAR
from strategy.shift_match_core import passes_gna_firewall, role_matches

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/match", tags=["semantic-match"])

TOP_K = 5


class SemanticMatchQueryIn(BaseModel):
    query: str = Field(..., min_length=8, max_length=2000)
    required_role: str | None = None
    facility_type: str | None = None
    facility_county: str | None = None
    shift_context: dict[str, Any] = Field(default_factory=dict)


class SemanticMatchCandidateOut(BaseModel):
    rank: int
    provider_id: str
    full_name: str
    credential_type: str
    county: str | None
    vetted_status: str
    similarity_score: float
    profile_preview: str


class SemanticMatchResponse(BaseModel):
    ok: bool = True
    query: str
    match_count: int
    candidates: list[SemanticMatchCandidateOut]
    embedding_model: str


class SyncEmbeddingsResponse(BaseModel):
    ok: bool = True
    synced: int
    skipped: int
    embedding_model: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _embedding_configured() -> bool:
    return bool(str(settings.OUTREACH_LLM_API_KEY or "").strip()) and bool(
        str(settings.OUTREACH_LLM_URL or "").strip()
    )


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if not _embedding_configured():
        raise HTTPException(status_code=503, detail="embedding_api_not_configured")

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
        "model": settings.SEMANTIC_EMBEDDING_MODEL,
        "input": texts,
    }
    try:
        with httpx.Client(timeout=settings.OUTREACH_LLM_TIMEOUT_SECONDS) as client:
            response = client.post(embed_url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Embedding API failed: %s", exc)
        raise HTTPException(status_code=502, detail="embedding_api_error") from exc

    rows = payload.get("data") or []
    if len(rows) != len(texts):
        raise HTTPException(status_code=502, detail="embedding_api_invalid_response")

    vectors: list[list[float]] = []
    for row in sorted(rows, key=lambda item: int(item.get("index", 0))):
        embedding = row.get("embedding")
        if not isinstance(embedding, list):
            raise HTTPException(status_code=502, detail="embedding_api_invalid_vector")
        if len(embedding) != settings.SEMANTIC_EMBEDDING_DIMENSIONS:
            raise HTTPException(status_code=502, detail="embedding_dimension_mismatch")
        vectors.append([float(value) for value in embedding])
    return vectors


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _build_provider_profile_text(db: Session, provider: MarylandProvider) -> str:
    compliance = (
        db.query(MdProviderCompliance)
        .filter(MdProviderCompliance.provider_id == provider.provider_id)
        .first()
    )
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


def _upsert_provider_embedding(db: Session, provider: MarylandProvider, profile_text: str, vector: list[float]) -> None:
    literal = _vector_literal(vector)
    db.execute(
        text(
            """
            INSERT INTO provider_profile_embeddings (provider_id, profile_text, embedding, updated_at)
            VALUES (:provider_id, :profile_text, CAST(:embedding AS vector), :updated_at)
            ON CONFLICT (provider_id) DO UPDATE SET
                profile_text = EXCLUDED.profile_text,
                embedding = EXCLUDED.embedding,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "provider_id": str(provider.provider_id),
            "profile_text": profile_text,
            "embedding": literal,
            "updated_at": _utc_now(),
        },
    )


def sync_provider_embeddings(db: Session) -> dict[str, int]:
    providers = (
        db.query(MarylandProvider)
        .filter(MarylandProvider.vetted_status == VETTED_CLEAR)
        .filter(MarylandProvider.dispatch_status == "ACTIVE")
        .all()
    )
    if not providers:
        return {"synced": 0, "skipped": 0}

    profile_rows: list[tuple[MarylandProvider, str]] = []
    for provider in providers:
        profile_rows.append((provider, _build_provider_profile_text(db, provider)))

    vectors = _embed_texts([row[1] for row in profile_rows])
    synced = 0
    for (provider, profile_text), vector in zip(profile_rows, vectors, strict=True):
        _upsert_provider_embedding(db, provider, profile_text, vector)
        synced += 1
    db.commit()
    return {"synced": synced, "skipped": 0}


def _pgvector_ready(db: Session) -> bool:
    row = db.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1")
    ).first()
    return row is not None


def search_semantic_matches(db: Session, payload: SemanticMatchQueryIn) -> SemanticMatchResponse:
    if not _pgvector_ready(db):
        raise HTTPException(status_code=503, detail="pgvector_not_enabled")

    count = db.execute(text("SELECT COUNT(*) FROM provider_profile_embeddings")).scalar() or 0
    if int(count) == 0:
        raise HTTPException(status_code=503, detail="provider_embeddings_not_synced")

    query_vector = _embed_texts([payload.query.strip()])[0]
    literal = _vector_literal(query_vector)

    rows = db.execute(
        text(
            """
            SELECT
                p.provider_id,
                p.full_name,
                p.credential_type,
                p.vetted_status,
                e.profile_text,
                1 - (e.embedding <=> CAST(:query_embedding AS vector)) AS similarity_score,
                c.home_county
            FROM provider_profile_embeddings e
            JOIN maryland_providers p ON p.provider_id = e.provider_id
            LEFT JOIN md_provider_compliance c ON c.provider_id = p.provider_id
            WHERE p.vetted_status = :vetted_clear
              AND p.dispatch_status = 'ACTIVE'
            ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :scan_limit
            """
        ),
        {
            "query_embedding": literal,
            "vetted_clear": VETTED_CLEAR,
            "scan_limit": max(TOP_K * 4, 20),
        },
    ).mappings().all()

    shift_context = {
        "required_role": payload.required_role or payload.shift_context.get("required_role"),
        "facility_type": payload.facility_type or payload.shift_context.get("facility_type"),
        "facility_county": payload.facility_county or payload.shift_context.get("facility_county"),
        "county": payload.facility_county or payload.shift_context.get("county"),
    }

    candidates: list[SemanticMatchCandidateOut] = []
    for row in rows:
        candidate_dict = {
            "provider_id": str(row["provider_id"]),
            "full_name": row["full_name"],
            "role": str(row["credential_type"] or "").upper(),
            "county": row["home_county"],
            "has_gna_endorsement": "GNA endorsement: True" in str(row["profile_text"]),
        }
        if shift_context.get("required_role") and not role_matches(candidate_dict, shift_context):
            continue
        if not passes_gna_firewall(candidate_dict, shift_context):
            continue

        candidates.append(
            SemanticMatchCandidateOut(
                rank=len(candidates) + 1,
                provider_id=str(row["provider_id"]),
                full_name=row["full_name"],
                credential_type=str(row["credential_type"] or ""),
                county=row["home_county"],
                vetted_status=str(row["vetted_status"] or ""),
                similarity_score=round(float(row["similarity_score"] or 0.0), 4),
                profile_preview=str(row["profile_text"])[:180] + "…",
            )
        )
        if len(candidates) >= TOP_K:
            break

    return SemanticMatchResponse(
        ok=True,
        query=payload.query.strip(),
        match_count=len(candidates),
        candidates=candidates,
        embedding_model=settings.SEMANTIC_EMBEDDING_MODEL,
    )


@router.post("/semantic-search", response_model=SemanticMatchResponse)
def semantic_shift_match(payload: SemanticMatchQueryIn, db: Session = Depends(get_db)) -> SemanticMatchResponse:
    return search_semantic_matches(db, payload)


@router.post(
    "/sync-embeddings",
    response_model=SyncEmbeddingsResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def sync_embeddings(db: Session = Depends(get_db)) -> SyncEmbeddingsResponse:
    result = sync_provider_embeddings(db)
    return SyncEmbeddingsResponse(
        ok=True,
        synced=result["synced"],
        skipped=result["skipped"],
        embedding_model=settings.SEMANTIC_EMBEDDING_MODEL,
    )


def register_vector_match_engine(app) -> None:
    app.include_router(router)
