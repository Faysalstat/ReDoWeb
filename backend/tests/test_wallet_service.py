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


def test_spend_locks_wallet_before_idempotency_check(db_session, monkeypatch):
    """Regression test: spend() must acquire the wallet's FOR UPDATE lock
    *before* checking the idempotency key, not after -- otherwise two
    concurrent calls with the same key can both pass the check and race to
    insert it, and the loser hits the DB's unique constraint on
    idempotency_key as an unhandled IntegrityError instead of quietly
    no-op'ing. This can't easily be tested with real thread concurrency
    against SQLite (no row locking), so instead it asserts the *order* of
    operations: the idempotency SELECT must not run before the wallet SELECT
    ... FOR UPDATE."""
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    call_order = []
    original_query = db_session.query

    def tracking_query(model):
        if model is CreditWallet:
            call_order.append("wallet_lock")
        elif model is CreditTransaction:
            call_order.append("idempotency_check")
        return original_query(model)

    monkeypatch.setattr(db_session, "query", tracking_query)

    wallet_service.spend(db_session, user.id, 1, "generation_spend", idempotency_key="k1")

    assert call_order[0] == "wallet_lock"
    assert "idempotency_check" in call_order
    assert call_order.index("wallet_lock") < call_order.index("idempotency_check")


def test_spend_creates_wallet_with_zero_balance_if_missing(db_session):
    user = _make_user(db_session)

    with pytest.raises(InsufficientCreditsError):
        wallet_service.spend(db_session, user.id, 1, "generation_spend")

    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).count() == 1


def test_admin_adjust_positive_increases_balance_and_writes_ledger_row(db_session):
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    wallet, txn = wallet_service.admin_adjust(db_session, user.id, 5)
    db_session.commit()

    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS + 5
    assert txn.amount == 5
    assert txn.reason == "admin_adjustment"


def test_admin_adjust_negative_decreases_balance(db_session):
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    wallet, txn = wallet_service.admin_adjust(db_session, user.id, -1)
    db_session.commit()

    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS - 1
    assert txn.amount == -1
    assert txn.reason == "admin_adjustment"


def test_admin_adjust_negative_below_zero_raises_and_writes_nothing(db_session):
    user = _make_user(db_session)
    wallet_service.get_or_create_wallet(db_session, user.id)  # balance 0
    db_session.commit()

    with pytest.raises(InsufficientCreditsError):
        wallet_service.admin_adjust(db_session, user.id, -1)

    wallet = db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).one()
    assert wallet.balance == 0
    assert (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id, CreditTransaction.reason == "admin_adjustment")
        .count()
        == 0
    )


def test_admin_adjust_is_idempotent_by_key(db_session):
    user = _make_user(db_session)
    wallet_service.grant_signup_credits(db_session, user.id)
    db_session.commit()

    key = "admin_adjustment:some-purchase-id"
    wallet_service.admin_adjust(db_session, user.id, 5, idempotency_key=key)
    db_session.commit()
    wallet, txn = wallet_service.admin_adjust(db_session, user.id, 5, idempotency_key=key)
    db_session.commit()

    assert wallet.balance == wallet_service.SIGNUP_GRANT_CREDITS + 5
    adjustment_txns = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id, CreditTransaction.reason == "admin_adjustment")
        .all()
    )
    assert len(adjustment_txns) == 1
    assert txn.id == adjustment_txns[0].id


def test_admin_adjust_creates_wallet_with_zero_balance_if_missing(db_session):
    user = _make_user(db_session)

    wallet, txn = wallet_service.admin_adjust(db_session, user.id, 3)
    db_session.commit()

    assert wallet.balance == 3
    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).count() == 1
