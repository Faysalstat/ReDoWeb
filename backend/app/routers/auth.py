from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..db.session import get_db
from ..models import User
from ..rate_limit import limiter
from ..schemas.auth import GoogleLoginRequest, TokenResponse, UserOut
from ..services import auth_service
from ..services.auth_service import AuthError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        # secure=False is fine for local dev over http://localhost; this must
        # become True before ever deploying behind real HTTPS.
        secure=False,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
    )


def _user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, is_admin=user.is_admin)


@router.post("/google", response_model=TokenResponse)
@limiter.limit(get_settings().rate_limit_auth)
def google_login(
    payload: GoogleLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    try:
        user, access_token, raw_refresh = auth_service.authenticate_google(payload.id_token, db)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token, user=_user_out(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        user, access_token, new_raw_refresh = auth_service.refresh_access_token(raw_token, db)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_refresh_cookie(response, new_raw_refresh)
    return TokenResponse(access_token=access_token, user=_user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token is not None:
        auth_service.logout(raw_token, db)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(current_user)
