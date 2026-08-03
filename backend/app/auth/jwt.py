import hashlib
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
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
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


def new_refresh_token() -> tuple[str, str, datetime]:
    """Returns (raw_token, token_hash, expires_at). Only the hash is ever
    persisted -- the raw value is handed to the client once (in the httpOnly
    cookie) and can't be recovered from the DB, so a leaked DB doesn't expose
    usable refresh tokens."""
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return raw_token, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
