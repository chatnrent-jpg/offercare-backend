"""Learn H_j (response propensity) and T_j (fatigue) from SMS + lock history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ClinicalPlacementLedger, MarylandProvider, ShiftNotificationLog


@dataclass(frozen=True)
class SniperScoreSnapshot:
    provider_id: UUID
    response_propensity: float
    fatigue_score: float
    notifications_total: int
    acceptances_total: int
    notifications_recent: int


def compute_response_propensity(
    *,
    notifications: int,
    acceptances: int,
    prior: float | None = None,
    prior_weight: float | None = None,
) -> float:
    base_prior = settings.SNIPER_PROPENSITY_PRIOR if prior is None else prior
    weight = settings.SNIPER_PROPENSITY_PRIOR_WEIGHT if prior_weight is None else prior_weight
    if notifications <= 0 and acceptances <= 0:
        return round(max(0.0, min(1.0, base_prior)), 3)
    score = (acceptances + base_prior * weight) / (notifications + weight)
    return round(max(0.0, min(1.0, score)), 3)


def compute_fatigue_score(
    *,
    recent_notifications: int,
    per_sms: float | None = None,
    max_fatigue: float | None = None,
) -> float:
    step = settings.SNIPER_FATIGUE_PER_SMS if per_sms is None else per_sms
    cap = settings.SNIPER_FATIGUE_MAX if max_fatigue is None else max_fatigue
    return round(min(cap, max(0.0, recent_notifications * step)), 2)


def _recent_cutoff() -> datetime:
    hours = settings.SNIPER_FATIGUE_WINDOW_HOURS
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def build_sniper_score_snapshot(db: Session, provider_id: UUID) -> SniperScoreSnapshot:
    notifications_total = (
        db.query(ShiftNotificationLog)
        .filter(ShiftNotificationLog.provider_id == provider_id)
        .count()
    )
    acceptances_total = (
        db.query(ClinicalPlacementLedger)
        .filter(ClinicalPlacementLedger.assigned_clinician_id == provider_id)
        .count()
    )
    notifications_recent = (
        db.query(ShiftNotificationLog)
        .filter(
            ShiftNotificationLog.provider_id == provider_id,
            ShiftNotificationLog.sent_at >= _recent_cutoff(),
        )
        .count()
    )
    return SniperScoreSnapshot(
        provider_id=provider_id,
        response_propensity=compute_response_propensity(
            notifications=notifications_total,
            acceptances=acceptances_total,
        ),
        fatigue_score=compute_fatigue_score(recent_notifications=notifications_recent),
        notifications_total=notifications_total,
        acceptances_total=acceptances_total,
        notifications_recent=notifications_recent,
    )


def refresh_provider_sniper_scores(
    db: Session,
    provider_id: UUID,
    *,
    commit: bool = True,
) -> SniperScoreSnapshot | None:
    if not settings.SNIPER_LEARNING_ENABLED:
        return None
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        return None
    db.flush()
    snapshot = build_sniper_score_snapshot(db, provider_id)
    provider.response_propensity = snapshot.response_propensity
    provider.fatigue_score = snapshot.fatigue_score
    db.add(provider)
    if commit:
        db.commit()
        db.refresh(provider)
    return snapshot


def list_provider_sniper_scores(db: Session) -> list[SniperScoreSnapshot]:
    return [
        build_sniper_score_snapshot(db, provider.provider_id)
        for provider in db.query(MarylandProvider).order_by(MarylandProvider.full_name).all()
    ]


def refresh_all_provider_sniper_scores(db: Session) -> list[SniperScoreSnapshot]:
    if not settings.SNIPER_LEARNING_ENABLED:
        return []
    snapshots: list[SniperScoreSnapshot] = []
    db.flush()
    for provider in db.query(MarylandProvider).all():
        snapshot = build_sniper_score_snapshot(db, provider.provider_id)
        provider.response_propensity = snapshot.response_propensity
        provider.fatigue_score = snapshot.fatigue_score
        db.add(provider)
        snapshots.append(snapshot)
    if snapshots:
        db.commit()
    return snapshots
