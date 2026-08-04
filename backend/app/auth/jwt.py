import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from ..config import get_settings


class InvalidTokenError(Exception):
    pass


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    """Returns the user id encoded in a valid, unexpired access token.
    Raises InvalidTokenError for anything else (expired, malformed, wrong
    signature)."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc


def new_oauth_state() -> str:
    """A short-lived CSRF nonce for the Google authorization-code redirect
    dance -- set in a cookie before redirecting to Google, compared against
    the value Google echoes back on the callback. Not a credential, so no
    hashing is needed (unlike the raw refresh tokens this replaced)."""
    return secrets.token_urlsafe(32)
