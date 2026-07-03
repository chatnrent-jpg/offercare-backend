"""Clinician portal authentication — email/password, Google, and Facebook."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ClinicianLoginRequest, ClinicianLoginResponse, PortalAuthProvidersResponse, ProviderRead
from app.services.portal_login import portal_demo_quick_login, portal_email_password_login
from app.services.portal_oauth import (
    exchange_oauth_code,
    facebook_authorize_url,
    google_authorize_url,
    oauth_error_message,
    oauth_providers_enabled,
    oauth_redirect_base,
    portal_home_url,
    portal_oauth_login,
    verify_oauth_state,
)

router = APIRouter(prefix="/api/portal/auth", tags=["portal-auth"])


def _portal_redirect(*, token: str | None = None, auth_error: str | None = None, message: str | None = None) -> RedirectResponse:
    if token:
        return RedirectResponse(url=portal_home_url(query=f"token={quote(token)}"), status_code=302)
    params = []
    if auth_error:
        params.append(f"auth_error={quote(auth_error)}")
    if message:
        params.append(f"auth_message={quote(message)}")
    query = "&".join(params)
    return RedirectResponse(url=portal_home_url(query=query), status_code=302)


@router.get("/providers", response_model=PortalAuthProvidersResponse)
def portal_auth_providers() -> PortalAuthProvidersResponse:
    enabled = oauth_providers_enabled()
    return PortalAuthProvidersResponse(
        google=enabled["google"],
        facebook=enabled["facebook"],
        demo=True,
        api_base=oauth_redirect_base(),
    )


@router.post("/login", response_model=ClinicianLoginResponse)
def portal_password_login(payload: ClinicianLoginRequest, db: Session = Depends(get_db)):
    try:
        provider, token = portal_email_password_login(
            db,
            email=str(payload.email),
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return ClinicianLoginResponse(
        access_token=token,
        provider=ProviderRead.model_validate(provider),
    )


@router.post("/demo-login", response_model=ClinicianLoginResponse)
def portal_demo_login(db: Session = Depends(get_db)):
    try:
        provider, token = portal_demo_quick_login(db)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return ClinicianLoginResponse(
        access_token=token,
        provider=ProviderRead.model_validate(provider),
    )


@router.get("/google/start")
def portal_google_start():
    try:
        return RedirectResponse(url=google_authorize_url(), status_code=302)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/google/callback")
async def portal_google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if error:
        return _portal_redirect(auth_error="oauth_denied", message="Google sign-in was cancelled.")
    if not code or not state:
        return _portal_redirect(auth_error="oauth_exchange_failed")
    try:
        verify_oauth_state(state, "google")
        profile = await exchange_oauth_code("google", code)
        _, token = portal_oauth_login(db, profile)
        return _portal_redirect(token=token)
    except ValueError as exc:
        code_key = str(exc)
        return _portal_redirect(auth_error=code_key, message=oauth_error_message(code_key))
    except Exception:
        return _portal_redirect(auth_error="oauth_exchange_failed", message=oauth_error_message("oauth_exchange_failed"))


@router.get("/facebook/start")
def portal_facebook_start():
    try:
        return RedirectResponse(url=facebook_authorize_url(), status_code=302)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/facebook/callback")
async def portal_facebook_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_reason: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if error or error_reason == "user_denied":
        return _portal_redirect(auth_error="oauth_denied", message="Facebook sign-in was cancelled.")
    if not code or not state:
        return _portal_redirect(auth_error="oauth_exchange_failed")
    try:
        verify_oauth_state(state, "facebook")
        profile = await exchange_oauth_code("facebook", code)
        _, token = portal_oauth_login(db, profile)
        return _portal_redirect(token=token)
    except ValueError as exc:
        code_key = str(exc)
        return _portal_redirect(auth_error=code_key, message=oauth_error_message(code_key))
    except Exception:
        return _portal_redirect(auth_error="oauth_exchange_failed", message=oauth_error_message("oauth_exchange_failed"))
