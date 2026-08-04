from sqlalchemy.orm import Session

from ..auth.jwt import create_access_token
from ..models import AuthIdentity, User
from . import wallet_service


class AuthError(Exception):
    pass


def authenticate_google(claims: dict, db: Session) -> tuple[User, str]:
    """Links/creates the local User + AuthIdentity from already-verified
    Google claims (verification + the authorization-code exchange happen in
    the router, since that's transport/protocol plumbing) and issues a fresh
    access token. Returns (user, access_token)."""
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
            wallet_service.grant_signup_credits(db, user.id)
        db.add(AuthIdentity(user_id=user.id, provider="google", provider_user_id=provider_user_id))

    if not user.is_active:
        raise AuthError("Account is disabled")

    access_token = create_access_token(user.id)
    db.commit()

    return user, access_token
