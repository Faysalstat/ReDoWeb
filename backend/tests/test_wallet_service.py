import pytest

from app.models import CreditTransaction, CreditWallet, User
from app.services import wallet_service
from app.services.wallet_service import InsufficientCreditsError


def _make_user(db_session, email="wallet-test@example.com") -> User:
    user = User(email=email, is_email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_grant_signup_credits_creates_wallet_with_balance(db_session):
    user = _make_user(db_session)

    wallet = wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS
    assert wallet.user_id == user.id


def test_grant_signup_credits_writes_one_ledger_row(db_session):
    user = _make_user(db_session)

    wallet = wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    transactions = db_session.query(CreditTransaction).filter(CreditTransaction.wallet_id == wallet.id).all()
    assert len(transactions) == 1
    assert transactions[0].amount == wallet_service.SIGNUP_GRANT_CREDITS
    assert transactions[0].reason == "signup_grant"
    assert transactions[0].idempotency_key == f"signup_grant:{user.id}"


def test_get_or_create_wallet_returns_existing_wallet(db_session):
    user = _make_user(db_session)
    created = wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    fetched = wallet_service.get_or_create_wallet(db_session, user.id)

    assert fetched.id == created.id
    assert fetched.balance == wallet_service.SIGNUP_GRANT_CREDITS
    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).count() == 1


def test_get_or_create_wallet_creates_missing_wallet_with_zero_balance(db_session):
    user = _make_user(db_session)

    wallet = wallet_service.get_or_create_wallet(db_session, user.id)
    db_session.commit()

    assert wallet.balance == 0
    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).count() == 1


def test_spend_deducts_balance_and_writes_negative_ledger_row(db_session):
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    wallet = wallet_service.spend(db_session, user.id, 1, "generation_spend")
    db_session.commit()

    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS - 1
    transactions = db_session.query(CreditTransaction).filter(CreditTransaction.wallet_id == wallet.id).all()
    spend_txn = next(t for t in transactions if t.reason == "generation_spend")
    assert spend_txn.amount == -1


def test_spend_raises_when_balance_insufficient(db_session):
    user = _make_user(db_session)
    wallet_service.get_or_create_wallet(db_session, user.id)  # balance 0
    db_session.commit()

    with pytest.raises(InsufficientCreditsError):
        wallet_service.spend(db_session, user.id, 1, "generation_spend")

    wallet = db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).one()
    assert wallet.balance == 0
    assert db_session.query(CreditTransaction).filter(CreditTransaction.wallet_id == wallet.id).count() == 0


def test_spend_exact_balance_succeeds_and_reaches_zero(db_session):
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    wallet = wallet_service.spend(
        db_session, user.id, wallet_service.SIGNUP_GRANT_CREDITS, "download_spend"
    )
    db_session.commit()

    assert wallet.balance == 0


def test_spend_is_idempotent_by_key(db_session):
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    key = "generation_spend:some-project-id"
    wallet_service.spend(db_session, user.id, 1, "generation_spend", idempotency_key=key)
    db_session.commit()
    wallet = wallet_service.spend(db_session, user.id, 1, "generation_spend", idempotency_key=key)
    db_session.commit()

    # Second call with the same key is a no-op -- balance only reflects one charge.
    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS - 1
    spend_txns = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id, CreditTransaction.reason == "generation_spend")
        .all()
    )
    assert len(spend_txns) == 1


def test_spend_creates_wallet_with_zero_balance_if_missing(db_session):
    user = _make_user(db_session)

    with pytest.raises(InsufficientCreditsError):
        wallet_service.spend(db_session, user.id, 1, "generation_spend")

    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).count() == 1
