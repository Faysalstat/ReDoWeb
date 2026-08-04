import uuid

from sqlalchemy.orm import Session

from ..models import CreditTransaction, CreditWallet

SIGNUP_GRANT_CREDITS = 3

# 1 credit is always spent on the initial generation, regardless of how many
# tiers are enabled -- see CLAUDE.md's "3 free signup credits are
# intentionally never enough to download anything" note. Download cost is
# per-tier instead (tier_service.Tier.download_credit_cost).
GENERATION_SPEND_CREDITS = 1


class InsufficientCreditsError(Exception):
    """Raised when a spend would take the wallet balance below zero."""


def get_or_create_wallet(db: Session, user_id: uuid.UUID) -> CreditWallet:
    """Defensive getter for the read path -- every real signup gets a wallet
    via grant_signup_credits(), but this keeps GET /credits/wallet from
    ever 500ing if one is somehow missing."""
    wallet = db.query(CreditWallet).filter(CreditWallet.user_id == user_id).one_or_none()
    if wallet is None:
        wallet = CreditWallet(user_id=user_id, balance=0)
        db.add(wallet)
        db.flush()
    return wallet


def grant_signup_credits(db: Session, user_id: uuid.UUID) -> CreditWallet:
    """Creates the wallet + a signup_grant ledger row for a brand-new user.
    Not committed here -- the caller (auth_service, creating the User +
    AuthIdentity in the same transaction) commits once at the end."""
    wallet = CreditWallet(user_id=user_id, balance=SIGNUP_GRANT_CREDITS)
    db.add(wallet)
    db.flush()

    db.add(
        CreditTransaction(
            wallet_id=wallet.id,
            amount=SIGNUP_GRANT_CREDITS,
            reason="signup_grant",
            idempotency_key=f"signup_grant:{user_id}",
        )
    )
    return wallet


def spend(
    db: Session,
    user_id: uuid.UUID,
    amount: int,
    reason: str,
    *,
    related_project_id: uuid.UUID | None = None,
    related_job_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> CreditWallet:
    """Row-locking credit spend -- credit_transactions is the ledger (ground
    truth), credit_wallets.balance is updated in the same DB transaction as
    a denormalized read cache. Raises InsufficientCreditsError (no partial
    spend, nothing written) if the wallet can't cover `amount`. Caller
    commits.

    `idempotency_key`, when given, makes repeat calls a no-op instead of a
    double-charge: if a transaction with that key already exists, the
    existing wallet is returned unchanged. This is what makes it safe to
    call this from a Celery task with no retry policy, and to let a second
    `POST /projects/{id}/download` for the same tier be a free re-download
    instead of a second charge.
    """
    if idempotency_key is not None:
        existing = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing is not None:
            return db.query(CreditWallet).filter(CreditWallet.id == existing.wallet_id).one()

    # SELECT ... FOR UPDATE: serializes concurrent spends against the same
    # wallet so two racing requests against a low balance can't both read
    # "sufficient" before either writes back the debit.
    wallet = (
        db.query(CreditWallet).filter(CreditWallet.user_id == user_id).with_for_update().one_or_none()
    )
    if wallet is None:
        wallet = CreditWallet(user_id=user_id, balance=0)
        db.add(wallet)
        db.flush()

    if wallet.balance < amount:
        raise InsufficientCreditsError(
            f"wallet {wallet.id} has {wallet.balance} credit(s), needs {amount}"
        )

    wallet.balance -= amount
    db.add(
        CreditTransaction(
            wallet_id=wallet.id,
            amount=-amount,
            reason=reason,
            related_project_id=related_project_id,
            related_job_id=related_job_id,
            idempotency_key=idempotency_key,
        )
    )
    db.flush()
    return wallet
