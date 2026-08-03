import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, hash_refresh_token
from app.models import AuthIdentity, RefreshToken, User
from app.services import auth_service
from app.services.auth_service import AuthError


def _make_user(db_session, email="user@example.com", is_active=True) -> User:
    user = User(email=email, is_email_verified=True, is_active=is_active)
    db_session.add(user)
    db_session.commit()
    return user


# -- authenticate_google -----------------------------------------------------


def test_authenticate_google_creates_new_user_and_identity(db_session):
    fake_claims = {
        "sub": "google-subject-123",
        "email": "new.user@example.com",
        "email_verified": True,
    }
    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", return_value=fake_claims):
        user, access_token, raw_refresh = auth_service.authenticate_google("fake-id-token", db_session)

    assert user.email == "new.user@example.com"
    assert user.is_email_verified is True
    assert access_token
    assert raw_refresh

    identity = db_session.query(AuthIdentity).filter(AuthIdentity.user_id == user.id).one()
    assert identity.provider == "google"
    assert identity.provider_user_id == "google-subject-123"

    stored_refresh = db_session.query(RefreshToken).filter(RefreshToken.user_id == user.id).one()
    assert stored_refresh.token_hash == hash_refresh_token(raw_refresh)


def test_authenticate_google_links_existing_user_by_verified_email(db_session):
    existing = _make_user(db_session, email="already.here@example.com")
    fake_claims = {"sub": "google-subject-456", "email": "already.here@example.com", "email_verified": True}

    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", return_value=fake_claims):
        user, _, _ = auth_service.authenticate_google("fake-id-token", db_session)

    assert user.id == existing.id
    assert db_session.query(User).count() == 1


def test_authenticate_google_rejects_unverified_email(db_session):
    fake_claims = {"sub": "google-subject-789", "email": "unverified@example.com", "email_verified": False}
    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", return_value=fake_claims):
        with pytest.raises(AuthError):
            auth_service.authenticate_google("fake-id-token", db_session)


def test_authenticate_google_rejects_disabled_account(db_session):
    _make_user(db_session, email="disabled@example.com", is_active=False)
    fake_claims = {"sub": "google-subject-999", "email": "disabled@example.com", "email_verified": True}
    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", return_value=fake_claims):
        with pytest.raises(AuthError):
            auth_service.authenticate_google("fake-id-token", db_session)


def test_authenticate_google_invalid_token_raises_auth_error(db_session):
    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token")):
        with pytest.raises(AuthError):
            auth_service.authenticate_google("garbage", db_session)


# -- refresh_access_token / logout (revocation + rotation) -------------------


def test_refresh_rotates_token_and_old_one_is_revoked(db_session):
    user = _make_user(db_session)
    fake_claims = {"sub": "sub-1", "email": user.email, "email_verified": True}
    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", return_value=fake_claims):
        _, _, raw_refresh = auth_service.authenticate_google("fake-id-token", db_session)

    _, new_access_token, new_raw_refresh = auth_service.refresh_access_token(raw_refresh, db_session)

    assert new_access_token
    assert new_raw_refresh != raw_refresh

    old_row = db_session.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw_refresh)).one()
    assert old_row.revoked_at is not None

    # The rotated (old) token can no longer be used to refresh again.
    with pytest.raises(AuthError):
        auth_service.refresh_access_token(raw_refresh, db_session)

    # But the newly issued one works.
    auth_service.refresh_access_token(new_raw_refresh, db_session)


def test_refresh_rejects_unknown_token(db_session):
    with pytest.raises(AuthError):
        auth_service.refresh_access_token("this-token-was-never-issued", db_session)


def test_refresh_rejects_expired_token(db_session):
    user = _make_user(db_session)
    expired = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token("expired-raw-token"),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(expired)
    db_session.commit()

    with pytest.raises(AuthError):
        auth_service.refresh_access_token("expired-raw-token", db_session)


def test_logout_revokes_token_and_is_idempotent(db_session):
    user = _make_user(db_session)
    fake_claims = {"sub": "sub-2", "email": user.email, "email_verified": True}
    with patch("app.services.auth_service.google_id_token.verify_oauth2_token", return_value=fake_claims):
        _, _, raw_refresh = auth_service.authenticate_google("fake-id-token", db_session)

    auth_service.logout(raw_refresh, db_session)
    row = db_session.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw_refresh)).one()
    assert row.revoked_at is not None

    # Calling logout again on an already-revoked token is a no-op, not an error.
    auth_service.logout(raw_refresh, db_session)

    with pytest.raises(AuthError):
        auth_service.refresh_access_token(raw_refresh, db_session)


# -- get_current_user dependency ---------------------------------------------


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_accepts_valid_token(db_session):
    user = _make_user(db_session)
    token = create_access_token(user.id)
    resolved = get_current_user(credentials=_bearer(token), db=db_session)
    assert resolved.id == user.id


def test_get_current_user_rejects_missing_credentials(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=None, db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_invalid_token(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_bearer("not-a-real-token"), db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_token_for_unknown_user(db_session):
    token = create_access_token(uuid.uuid4())
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_bearer(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_inactive_user(db_session):
    user = _make_user(db_session, is_active=False)
    token = create_access_token(user.id)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_bearer(token), db=db_session)
    assert exc_info.value.status_code == 401
