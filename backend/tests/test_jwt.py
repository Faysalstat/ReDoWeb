import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.auth.jwt import InvalidTokenError, create_access_token, decode_access_token, new_oauth_state
from app.config import get_settings


def test_access_token_round_trip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_rejects_garbage_token():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-real-jwt")


def test_decode_rejects_wrong_signature():
    settings = get_settings()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=5)},
        "a-different-secret",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_rejects_expired_token():
    settings = get_settings()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    expired_token = pyjwt.encode(
        {"sub": str(user_id), "iat": now - timedelta(minutes=30), "exp": now - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(expired_token)


def test_decode_rejects_missing_subject_claim():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {"iat": now, "exp": now + timedelta(minutes=5)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_new_oauth_state_is_unique_each_call():
    assert new_oauth_state() != new_oauth_state()
