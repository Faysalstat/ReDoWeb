"""Orchestrates admin-issued credit adjustments: pairs a wallet_service
ledger write with a Purchase(source="manual_admin") row so the adjustment
shows up in revenue/earnings reporting and carries a human-readable note +
which admin issued it. Kept separate from wallet_service.py, which stays a
pure ledger primitive with no Purchase/admin-identity awareness -- the same
separation this codebase already uses between wallet_service and the task
layer that orchestrates it (e.g. tasks_generate.py calling wallet_service.
spend() alongside its own GenerationJob/Project writes)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import CreditTransaction, CreditWallet, Purchase
from . import wallet_service


@dataclass
class AdjustmentResult:
    wallet: CreditWallet
    transaction: CreditTransaction
    purchase: Purchase


def issue_adjustment(
    db: Session,
    *,
    user_id: uuid.UUID,
    amount: int,
    note: str,
    admin_id: uuid.UUID,
    related_project_id: uuid.UUID | None = None,
) -> AdjustmentResult:
    """Admin-facing credit grant/clawback. `amount` is a signed delta
    (positive grants, negative claws back) -- validated nonzero at the
    router/schema layer, not here. `note` is mandatory (empty/whitespace
    raises ValueError) since this is a human-initiated, audited action with
    no fixed reason enum the way spend() has.

    Writes a Purchase(source="manual_admin", amount_usd_cents=0,
    credits_granted=amount, note=note, created_by_admin_id=admin_id) for
    audit/revenue-reporting traceability, then a CreditTransaction via
    wallet_service.admin_adjust() with an idempotency_key derived from the
    Purchase's id (ties the ledger row 1:1 to this specific Purchase --
    mostly defense-in-depth, since a Purchase row is never retried the way
    a queued task might be). Caller commits.
    """
    if not note or not note.strip():
        raise ValueError("note is required for an admin credit adjustment")

    purchase = Purchase(
        user_id=user_id,
        amount_usd_cents=0,
        credits_granted=amount,
        status="completed",
        source="manual_admin",
        note=note,
        created_by_admin_id=admin_id,
    )
    db.add(purchase)
    db.flush()

    idempotency_key = f"admin_adjustment:{purchase.id}"
    wallet, txn = wallet_service.admin_adjust(
        db,
        user_id,
        amount,
        related_project_id=related_project_id,
        idempotency_key=idempotency_key,
    )
    txn.related_purchase_id = purchase.id
    db.flush()

    return AdjustmentResult(wallet=wallet, transaction=txn, purchase=purchase)
