import uuid

import pytest

from app.models import CreditWallet, Purchase, User
from app.services import admin_credits_service, wallet_service


def _make_user(db_session, email="admin-credits-test@example.com") -> User:
    user = User(email=email, is_email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_issue_adjustment_grants_credits_and_writes_purchase(db_session):
    user = _make_user(db_session)
    admin = _make_user(db_session, email="admin@example.com")
    wallet_service.get_or_create_wallet(db_session, user.id)
    db_session.commit()

    result = admin_credits_service.issue_adjustment(
        db_session, user_id=user.id, amount=5, note="goodwill credit for failed run", admin_id=admin.id
    )
    db_session.commit()

    assert result.wallet.balance == 5
    assert result.transaction.amount == 5
    assert result.transaction.reason == "admin_adjustment"
    assert result.transaction.related_purchase_id == result.purchase.id

    purchase = db_session.query(Purchase).filter(Purchase.id == result.purchase.id).one()
    assert purchase.source == "manual_admin"
    assert purchase.credits_granted == 5
    assert purchase.amount_usd_cents == 0
    assert purchase.note == "goodwill credit for failed run"
    assert purchase.created_by_admin_id == admin.id


def test_issue_adjustment_negative_clawback(db_session):
    user = _make_user(db_session)
    admin = _make_user(db_session, email="admin@example.com")
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    result = admin_credits_service.issue_adjustment(
        db_session, user_id=user.id, amount=-1, note="correcting over-grant", admin_id=admin.id
    )
    db_session.commit()

    assert result.wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS - 1
    assert result.purchase.credits_granted == -1


def test_issue_adjustment_rejects_empty_note(db_session):
    user = _make_user(db_session)
    admin = _make_user(db_session, email="admin@example.com")
    wallet_service.get_or_create_wallet(db_session, user.id)
    db_session.commit()

    with pytest.raises(ValueError):
        admin_credits_service.issue_adjustment(
            db_session, user_id=user.id, amount=5, note="   ", admin_id=admin.id
        )

    assert db_session.query(Purchase).filter(Purchase.user_id == user.id).count() == 0


def test_issue_adjustment_that_would_go_negative_raises_and_writes_nothing(db_session):
    user = _make_user(db_session)
    admin = _make_user(db_session, email="admin@example.com")
    wallet_service.get_or_create_wallet(db_session, user.id)  # balance 0
    db_session.commit()

    with pytest.raises(wallet_service.InsufficientCreditsError):
        admin_credits_service.issue_adjustment(
            db_session, user_id=user.id, amount=-1, note="oops", admin_id=admin.id
        )
    # Mirrors production: get_db's session is never committed on an
    # exception, and closing an uncommitted session rolls it back -- so the
    # Purchase flushed before admin_adjust() raised never actually persists.
    db_session.rollback()

    wallet = db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).one()
    assert wallet.balance == 0
    assert db_session.query(Purchase).filter(Purchase.user_id == user.id).count() == 0
