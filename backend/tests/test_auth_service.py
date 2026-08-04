import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.models import AuthIdentity, CreditWallet, User
from app.services import auth_service, wallet_service
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
    user, access_token = auth_service.authenticate_google(fake_claims, db_session)

    assert user.email == "new.user@example.com"
    assert user.is_email_verified is True
    assert access_token

    identity = db_session.query(AuthIdentity).filter(AuthIdentity.user_id == user.id).one()
    assert identity.provider == "google"
    assert identity.provider_user_id == "google-subject-123"

    wallet = db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).one()
    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS


def test_authenticate_google_links_existing_user_by_verified_email(db_session):
    existing = _make_user(db_session, email="already.here@example.com")
    fake_claims = {"sub": "google-subject-456", "email": "already.here@example.com", "email_verified": True}

    user, _ = auth_service.authenticate_google(fake_claims, db_session)

    assert user.id == existing.id
    # Linking an existing user must not mint a second signup grant/wallet.
    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).count() == 0
    assert db_session.query(User).count() == 1


def test_authenticate_google_rejects_unverified_email(db_session):
    fake_claims = {"sub": "google-subject-789", "email": "unverified@example.com", "email_verified": False}
    with pytest.raises(AuthError):
        auth_service.authenticate_google(fake_claims, db_session)


def test_authenticate_google_rejects_disabled_account(db_session):
    _make_user(db_session, email="disabled@example.com", is_active=False)
    fake_claims = {"sub": "google-subject-999", "email": "disabled@example.com", "email_verified": True}
    with pytest.raises(AuthError):
        auth_service.authenticate_google(fake_claims, db_session)


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
