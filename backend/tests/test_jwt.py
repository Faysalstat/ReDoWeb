import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.auth.jwt import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_refresh_token,
    new_refresh_token,
)
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


def test_new_refresh_token_hash_matches_and_expiry_in_range():
    settings = get_settings()
    before = datetime.now(timezone.utc)
    raw_token, token_hash, expires_at = new_refresh_token()

    assert hash_refresh_token(raw_token) == token_hash
    assert token_hash != raw_token

    expected_expiry = before + timedelta(days=settings.refresh_token_expire_days)
    assert abs((expires_at - expected_expiry).total_seconds()) < 5


def test_new_refresh_token_is_unique_each_call():
    raw_a, hash_a, _ = new_refresh_token()
    raw_b, hash_b, _ = new_refresh_token()
    assert raw_a != raw_b
    assert hash_a != hash_b
