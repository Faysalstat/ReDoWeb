from datetime import datetime, timezone

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from ..auth.jwt import create_access_token, hash_refresh_token, new_refresh_token
from ..config import get_settings
from ..models import AuthIdentity, RefreshToken, User


class AuthError(Exception):
    pass


def _as_aware_utc(value: datetime) -> datetime:
    """Some DB backends (e.g. SQLite, used in tests) drop tzinfo on
    round-trip even for timezone-aware columns; Postgres doesn't. Normalizing
    here keeps the expiry comparison correct on both."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def authenticate_google(id_token_str: str, db: Session) -> tuple[User, str, str]:
    """Verifies a Google Identity Services ID token, links/creates the local
    User + AuthIdentity, and issues a fresh access/refresh token pair.
    Returns (user, access_token, raw_refresh_token)."""
    settings = get_settings()
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), audience=settings.google_client_id
        )
    except ValueError as exc:
        raise AuthError(f"Invalid Google ID token: {exc}") from exc

    if not claims.get("email_verified", False):
        raise AuthError("Google account email is not verified")

    provider_user_id = claims["sub"]
    email = claims["email"]

    identity = (
        db.query(AuthIdentity)
        .filter(AuthIdentity.provider == "google", AuthIdentity.provider_user_id == provider_user_id)
        .one_or_none()
    )

    if identity is not None:
        user = identity.user
    else:
        # Link by verified email if this Google account matches an existing
        # user, else create a new pre-verified user -- matches
        # implementation-plan.md's documented Google OAuth linking behavior.
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(email=email, is_email_verified=True)
            db.add(user)
            db.flush()
        db.add(AuthIdentity(user_id=user.id, provider="google", provider_user_id=provider_user_id))

    if not user.is_active:
        raise AuthError("Account is disabled")

    access_token = create_access_token(user.id)
    raw_refresh, refresh_hash, expires_at = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=expires_at))
    db.commit()

    return user, access_token, raw_refresh


def refresh_access_token(raw_token: str, db: Session) -> tuple[User, str, str]:
    """Validates + rotates a refresh token: the presented token is revoked and
    a new one is issued, so a stolen-but-since-rotated token can't be replayed."""
    token_hash = hash_refresh_token(raw_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).one_or_none()
    if row is None or row.revoked_at is not None or _as_aware_utc(row.expires_at) < datetime.now(timezone.utc):
        raise AuthError("Invalid or expired refresh token")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AuthError("Invalid or expired refresh token")

    row.revoked_at = datetime.now(timezone.utc)

    access_token = create_access_token(user.id)
    new_raw, new_hash, new_expires_at = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=new_hash, expires_at=new_expires_at))
    db.commit()

    return user, access_token, new_raw


def logout(raw_token: str, db: Session) -> None:
    token_hash = hash_refresh_token(raw_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
