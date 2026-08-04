from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.jwt import new_oauth_state
from ..config import get_settings
from ..db.session import get_db
from ..models import User
from ..rate_limit import limiter
from ..schemas.auth import UserOut
from ..services import auth_service
from ..services.auth_service import AuthError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

OAUTH_STATE_COOKIE_NAME = "oauth_state"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, is_admin=user.is_admin)


def _exchange_code_for_claims(code: str) -> dict:
    """Exchanges an authorization code for Google tokens and returns the
    verified id_token claims. Raises AuthError on any transport/verification
    failure -- split out from google_callback so it's directly unit-testable
    without spinning up a full request/app."""
    settings = get_settings()
    try:
        token_response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10.0,
        )
        token_response.raise_for_status()
        id_token_str = token_response.json()["id_token"]
        return google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), audience=settings.google_client_id
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AuthError("Google sign-in failed") from exc


@router.get("/google/authorize")
@limiter.limit(get_settings().rate_limit_auth)
def google_authorize(request: Request) -> RedirectResponse:
    """Starts the Google OAuth2 authorization-code flow: sets a short-lived
    CSRF state cookie and redirects the browser to Google's consent screen."""
    settings = get_settings()
    state = new_oauth_state()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    redirect = RedirectResponse(url=f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", status_code=302)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=state,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=300,
    )
    return redirect


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Google redirects here with ?code=&state=. Exchanges the code for
    tokens, verifies the id_token, links/creates the user, then redirects the
    browser to the frontend's /auth/callback with the issued JWT."""
    settings = get_settings()
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE_NAME)

    def _error_redirect(message: str) -> RedirectResponse:
        redirect = RedirectResponse(
            url=f"{settings.frontend_url}/auth/callback?{urlencode({'error': message})}", status_code=302
        )
        redirect.delete_cookie(OAUTH_STATE_COOKIE_NAME)
        return redirect

    if not code or not state or not cookie_state or state != cookie_state:
        return _error_redirect("Invalid or expired login attempt")

    try:
        claims = _exchange_code_for_claims(code)
        _user, access_token = auth_service.authenticate_google(claims, db)
    except AuthError as exc:
        return _error_redirect(str(exc))

    redirect = RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?{urlencode({'token': access_token})}", status_code=302
    )
    redirect.delete_cookie(OAUTH_STATE_COOKIE_NAME)
    return redirect


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(current_user)
