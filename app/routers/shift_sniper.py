from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.config import settings
from app.models import MarylandProvider
from app.database import get_db
from app.schemas import (
    CascadeAdvanceRequest,
    CascadeAdvanceResponse,
    CascadeRecipientOut,
    CascadeStatusResponse,
    NotifyRequest,
    NotifyResponse,
    OfferRankResponse,
    ShiftLockResponse,
    SimulateReplyRequest,
    SniperClinicianScoreOut,
    SniperRelearnResponse,
    SniperScoreOut,
)
from app.services.shift_cascade import advance_cascade, get_cascade_status
from app.services.shift_lock import lock_shift_from_sms_reply, twiml_reply
from app.services.shift_ranking import notify_top_clinicians_for_offer, rank_offer_from_db
from app.services.sniper_learning import (
    list_provider_sniper_scores,
    refresh_all_provider_sniper_scores,
)
from app.services.twilio_security import validate_twilio_inbound_request
from app.shift_sniper import saint_judes_icu_demo

router = APIRouter(prefix="/shift-sniper", tags=["shift-sniper"])


def _cascade_response(status) -> CascadeStatusResponse:
    return CascadeStatusResponse(
        offer_id=status.offer_id,
        offer_status=status.offer_status,
        cascade_enabled=status.cascade_enabled,
        timeout_seconds=status.timeout_seconds,
        notified_count=status.notified_count,
        max_recipients=status.max_recipients,
        last_notified_at=status.last_notified_at,
        next_eligible_at=status.next_eligible_at,
        seconds_until_eligible=status.seconds_until_eligible,
        notified=[
            CascadeRecipientOut(
                provider_id=row.provider_id,
                full_name=row.full_name,
                phone_number=row.phone_number,
                rank=row.rank,
                notified_at=row.notified_at,
            )
            for row in status.notified
        ],
        next_candidate=(
            CascadeRecipientOut(
                provider_id=status.next_candidate.provider_id,
                full_name=status.next_candidate.full_name,
                phone_number=status.next_candidate.phone_number,
                rank=status.next_candidate.rank,
            )
            if status.next_candidate
            else None
        ),
        can_advance=status.can_advance,
    )


@router.get("/demo")
def shift_sniper_demo():
    return saint_judes_icu_demo()


@router.get("/offers/{offer_id}/rank", response_model=OfferRankResponse)
def rank_offer(offer_id: UUID, db: Session = Depends(get_db)):
    try:
        return rank_offer_from_db(db, offer_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="offer_not_found") from None


@router.post("/offers/{offer_id}/notify", response_model=NotifyResponse, dependencies=[Depends(require_admin_api_key)])
def notify_offer(offer_id: UUID, payload: NotifyRequest, db: Session = Depends(get_db)):
    try:
        return notify_top_clinicians_for_offer(
            db,
            offer_id,
            max_recipients=payload.max_recipients,
            reply_keyword=payload.reply_keyword,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="offer_not_found") from None


@router.get(
    "/offers/{offer_id}/cascade",
    response_model=CascadeStatusResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def cascade_status(offer_id: UUID, db: Session = Depends(get_db)):
    try:
        return _cascade_response(get_cascade_status(db, offer_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="offer_not_found") from None


@router.post(
    "/offers/{offer_id}/cascade",
    response_model=CascadeAdvanceResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def cascade_advance(offer_id: UUID, payload: CascadeAdvanceRequest, db: Session = Depends(get_db)):
    try:
        result = advance_cascade(
            db,
            offer_id,
            reply_keyword=payload.reply_keyword,
            force=payload.force,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="offer_not_found") from None
    return CascadeAdvanceResponse(
        status=result.status,
        message=result.message,
        delivery=result.delivery,
        cascade=_cascade_response(result.cascade),
    )


def _lock_response(result) -> ShiftLockResponse:
    return ShiftLockResponse(
        status=result.status,
        message=result.message,
        offer_id=result.offer_id,
        provider_id=result.provider_id,
        placement_id=result.placement_id,
    )


@router.post("/simulate-reply", response_model=ShiftLockResponse, dependencies=[Depends(require_admin_api_key)])
def simulate_sms_reply(payload: SimulateReplyRequest, db: Session = Depends(get_db)):
    """Local dev — mimic a clinician texting YES without Twilio."""
    result = lock_shift_from_sms_reply(
        db,
        from_phone=payload.phone_number,
        message_body=payload.body,
        reply_keyword=settings.TWILIO_REPLY_KEYWORD,
    )
    return _lock_response(result)


@router.post("/twilio/sms")
async def twilio_inbound_sms(request: Request, db: Session = Depends(get_db)):
    """Twilio webhook — wire your inbound SMS URL to this endpoint."""
    params = await validate_twilio_inbound_request(request)
    result = lock_shift_from_sms_reply(
        db,
        from_phone=params.get("From", ""),
        message_body=params.get("Body", ""),
        reply_keyword=settings.TWILIO_REPLY_KEYWORD,
    )
    return Response(content=twiml_reply(result.message), media_type="application/xml")


def _score_rows(db: Session, snapshots) -> list[SniperClinicianScoreOut]:
    if not snapshots:
        return []
    provider_ids = [row.provider_id for row in snapshots]
    providers = {
        row.provider_id: row
        for row in db.query(MarylandProvider).filter(MarylandProvider.provider_id.in_(provider_ids)).all()
    }
    rows: list[SniperClinicianScoreOut] = []
    for snapshot in snapshots:
        provider = providers.get(snapshot.provider_id)
        if provider is None:
            continue
        rows.append(
            SniperClinicianScoreOut(
                provider_id=snapshot.provider_id,
                full_name=provider.full_name,
                license_status=provider.license_status,
                phone_number=provider.phone_number,
                response_propensity=snapshot.response_propensity,
                fatigue_score=snapshot.fatigue_score,
                notifications_total=snapshot.notifications_total,
                acceptances_total=snapshot.acceptances_total,
                notifications_recent=snapshot.notifications_recent,
            )
        )
    return rows


@router.get("/scores", response_model=list[SniperClinicianScoreOut], dependencies=[Depends(require_admin_api_key)])
def list_sniper_scores(db: Session = Depends(get_db)):
    return _score_rows(db, list_provider_sniper_scores(db))


@router.post("/relearn-scores", response_model=SniperRelearnResponse, dependencies=[Depends(require_admin_api_key)])
def relearn_sniper_scores(db: Session = Depends(get_db)):
    snapshots = refresh_all_provider_sniper_scores(db)
    providers = [
        SniperScoreOut(
            provider_id=row.provider_id,
            response_propensity=row.response_propensity,
            fatigue_score=row.fatigue_score,
            notifications_total=row.notifications_total,
            acceptances_total=row.acceptances_total,
            notifications_recent=row.notifications_recent,
        )
        for row in snapshots
    ]
    return SniperRelearnResponse(updated=len(providers), providers=providers)
