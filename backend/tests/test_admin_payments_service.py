"""Admin purchase actions (services/admin_payments_service.py) and the
billing_service.recheck_purchase they build on. PayPal is faked at the
module boundary; the crediting rules are the real ones."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import CreditTransaction, CreditWallet, Purchase, User
from app.payments import paypal_client
from app.payments.paypal_client import PayPalError, PayPalNotConfiguredError
from app.services import admin_payments_service, wallet_service
from app.services.admin_payments_service import PurchaseActionNotAllowedError

OLD = datetime.now(timezone.utc) - timedelta(days=2)


def _order(status="COMPLETED", capture_status="COMPLETED", value="10.00"):
    order = {"id": "ORDER-1", "status": status, "purchase_units": [{}]}
    if capture_status is not None:
        order["purchase_units"] = [
            {"payments": {"captures": [{"id": "CAP-1", "status": capture_status,
                                        "amount": {"value": value, "currency_code": "USD"}}]}}
        ]
    return order


@pytest.fixture
def paypal(monkeypatch):
    """`order` is what get_order answers (dict or exception); capture_order
    answers with a completed capture."""
    state = {"order": _order(), "captures": 0}

    def get_order(order_id):
        if isinstance(state["order"], Exception):
            raise state["order"]
        return state["order"]

    def capture_order(order_id):
        state["captures"] += 1
        return _order()

    monkeypatch.setattr(paypal_client, "get_order", get_order)
    monkeypatch.setattr(paypal_client, "capture_order", capture_order)
    return state


@pytest.fixture
def people(db_session):
    buyer = User(email="buyer@example.com", is_email_verified=True)
    admin = User(email="admin@example.com", is_email_verified=True, is_admin=True)
    db_session.add_all([buyer, admin])
    db_session.commit()
    return buyer, admin


def _purchase(db, buyer, *, status="pending", created_at=OLD, source="paypal") -> Purchase:
    purchase = Purchase(
        user_id=buyer.id, amount_usd_cents=1000, credits_granted=10, status=status, source=source,
        paypal_order_id=f"ORDER-{uuid.uuid4().hex[:6]}", created_at=created_at,
    )
    db.add(purchase)
    db.commit()
    return purchase


def _balance(db, user) -> int:
    wallet = db.query(CreditWallet).filter(CreditWallet.user_id == user.id).one_or_none()
    return wallet.balance if wallet else 0


def _set_balance(db, user, balance):
    db.add(CreditWallet(user_id=user.id, balance=balance))
    db.commit()


def _completed_with_credits(db, buyer) -> Purchase:
    """A completed purchase whose credits really landed in the wallet."""
    purchase = _purchase(db, buyer)
    wallet_service.grant_purchase_credits(db, buyer.id, 10, purchase_id=purchase.id,
                                          idempotency_key=f"purchase:{purchase.id}")
    purchase.status = "completed"
    db.commit()
    return purchase


# --- re-check ------------------------------------------------------------------


def test_recheck_pending_with_completed_capture_grants_once(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)

    first = admin_payments_service.recheck(db_session, purchase.id, admin.id)
    second = admin_payments_service.recheck(db_session, purchase.id, admin.id)
    db_session.commit()

    assert first.status == "completed" and second.status == "completed"
    assert _balance(db_session, buyer) == 10
    assert db_session.query(CreditTransaction).filter(CreditTransaction.reason == "purchase").count() == 1
    assert purchase.resolved_by_admin_id == admin.id
    assert purchase.resolved_at is not None


def test_recheck_approved_order_captures_then_grants(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    paypal["order"] = _order(status="APPROVED", capture_status=None)

    outcome = admin_payments_service.recheck(db_session, purchase.id, admin.id)

    assert outcome.status == "completed"
    assert paypal["captures"] == 1
    assert _balance(db_session, buyer) == 10


def test_recheck_never_approved_stays_pending(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    paypal["order"] = _order(status="CREATED", capture_status=None)

    outcome = admin_payments_service.recheck(db_session, purchase.id, admin.id)

    assert outcome.status == "pending"
    assert purchase.status == "pending"
    assert _balance(db_session, buyer) == 0


@pytest.mark.parametrize(
    "answer",
    [_order(status="VOIDED", capture_status=None), PayPalError("gone", status_code=404, issue="RESOURCE_NOT_FOUND")],
)
def test_recheck_voided_or_expired_marks_failed(db_session, paypal, people, answer):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    paypal["order"] = answer

    outcome = admin_payments_service.recheck(db_session, purchase.id, admin.id)

    assert outcome.status == "failed"
    assert purchase.status == "failed"


def test_recheck_completed_purchase_detects_dashboard_refund(db_session, paypal, people):
    buyer, admin = people
    purchase = _completed_with_credits(db_session, buyer)
    paypal["order"] = _order(capture_status="REFUNDED")

    outcome = admin_payments_service.recheck(db_session, purchase.id, admin.id)

    assert outcome.status == "refunded"
    assert purchase.status == "refunded"
    assert purchase.refunded_at is not None
    assert _balance(db_session, buyer) == 10  # credits untouched


def test_recheck_completed_purchase_still_paid_is_unchanged(db_session, paypal, people):
    buyer, admin = people
    purchase = _completed_with_credits(db_session, buyer)

    outcome = admin_payments_service.recheck(db_session, purchase.id, admin.id)

    assert outcome.status == "completed"
    assert purchase.refunded_at is None


def test_recheck_without_paypal_keys_raises_not_configured(db_session, people, monkeypatch):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_ID", "")
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(PayPalNotConfiguredError):
        admin_payments_service.recheck(db_session, purchase.id, admin.id)
    assert purchase.status == "pending"


def test_recheck_timeout_raises_and_changes_nothing(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    paypal["order"] = PayPalError("slow", transient=True)

    with pytest.raises(PayPalError):
        admin_payments_service.recheck(db_session, purchase.id, admin.id)
    assert purchase.status == "pending"


def test_recheck_test_purchase_uses_mock_gateway(db_session, people, monkeypatch):
    buyer, admin = people
    purchase = _purchase(db_session, buyer, source="mock")
    purchase.paypal_order_id = f"MOCK-{purchase.id}-1000"
    db_session.commit()
    monkeypatch.setattr(paypal_client, "get_order", lambda order_id: pytest.fail("must not call PayPal"))

    outcome = admin_payments_service.recheck(db_session, purchase.id, admin.id)

    assert outcome.status == "completed"
    assert _balance(db_session, buyer) == 10


def test_recheck_rejects_manual_adjustments(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer, source="manual_admin", status="completed")

    with pytest.raises(PurchaseActionNotAllowedError):
        admin_payments_service.recheck(db_session, purchase.id, admin.id)


def test_webhook_refund_sets_refunded_at(db_session, paypal, people):
    from app.services import billing_service

    buyer, _ = people
    purchase = _completed_with_credits(db_session, buyer)
    purchase.paypal_capture_id = "CAP-9"
    db_session.commit()

    billing_service.handle_webhook_event(db_session, {
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "resource": {"id": "R-1", "links": [{"rel": "up", "href": "https://x/v2/payments/captures/CAP-9"}]},
    })

    assert purchase.status == "refunded"
    assert purchase.refunded_at is not None


# --- take back credits ---------------------------------------------------------


def _refunded(db, buyer) -> Purchase:
    purchase = _completed_with_credits(db, buyer)
    purchase.status = "refunded"
    db.commit()
    return purchase


def test_take_back_removes_credits_once(db_session, people):
    buyer, admin = people
    purchase = _refunded(db_session, buyer)

    first = admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "refunded in PayPal")
    second = admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "again")
    db_session.commit()

    assert (first.taken_back, first.requested, first.balance_after, first.already_done) == (10, 10, 0, False)
    assert (second.taken_back, second.already_done) == (10, True)
    assert _balance(db_session, buyer) == 0
    clawbacks = db_session.query(CreditTransaction).filter(
        CreditTransaction.idempotency_key == admin_payments_service.clawback_key(purchase.id)
    ).all()
    assert len(clawbacks) == 1
    assert clawbacks[0].related_purchase_id == purchase.id
    assert purchase.resolved_by_admin_id == admin.id


def test_take_back_is_capped_at_balance(db_session, people):
    buyer, admin = people
    purchase = _refunded(db_session, buyer)
    wallet_service.spend(db_session, buyer.id, 7, "download_spend")
    db_session.commit()

    result = admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "partial")

    assert (result.taken_back, result.requested, result.balance_after) == (3, 10, 0)


def test_take_back_with_zero_balance_writes_nothing_and_can_retry(db_session, people):
    buyer, admin = people
    purchase = _refunded(db_session, buyer)
    wallet_service.spend(db_session, buyer.id, 10, "download_spend")
    db_session.commit()

    empty = admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "nothing left")
    assert empty.taken_back == 0
    assert db_session.query(CreditTransaction).filter(
        CreditTransaction.idempotency_key == admin_payments_service.clawback_key(purchase.id)
    ).count() == 0

    wallet_service.admin_adjust(db_session, buyer.id, 4)
    db_session.commit()
    retry = admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "after top-up")
    assert retry.taken_back == 4


@pytest.mark.parametrize("status", ["pending", "completed", "failed"])
def test_take_back_only_for_refunded(db_session, people, status):
    buyer, admin = people
    purchase = _purchase(db_session, buyer, status=status)

    with pytest.raises(PurchaseActionNotAllowedError):
        admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "note")


def test_take_back_requires_note(db_session, people):
    buyer, admin = people
    purchase = _refunded(db_session, buyer)

    with pytest.raises(ValueError):
        admin_payments_service.take_back_credits(db_session, purchase.id, admin.id, "   ")


# --- mark as failed --------------------------------------------------------------


def test_mark_failed_when_buyer_never_approved(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    paypal["order"] = _order(status="CREATED", capture_status=None)

    result = admin_payments_service.mark_failed(db_session, purchase.id, admin.id, "abandoned")

    assert result.marked_failed is True
    assert purchase.status == "failed"
    assert "abandoned" in purchase.note
    assert _balance(db_session, buyer) == 0


def test_mark_failed_refuses_and_credits_when_actually_paid(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer)

    result = admin_payments_service.mark_failed(db_session, purchase.id, admin.id, "looks stuck")

    assert result.marked_failed is False
    assert result.outcome.status == "completed"
    assert purchase.status == "completed"
    assert _balance(db_session, buyer) == 10


def test_mark_failed_refuses_recent_checkout(db_session, paypal, people):
    buyer, admin = people
    purchase = _purchase(db_session, buyer, created_at=datetime.now(timezone.utc) - timedelta(hours=2))

    with pytest.raises(PurchaseActionNotAllowedError):
        admin_payments_service.mark_failed(db_session, purchase.id, admin.id, "too soon")


@pytest.mark.parametrize("status", ["completed", "failed", "refunded"])
def test_mark_failed_only_for_pending(db_session, paypal, people, status):
    buyer, admin = people
    purchase = _purchase(db_session, buyer, status=status)

    with pytest.raises(PurchaseActionNotAllowedError):
        admin_payments_service.mark_failed(db_session, purchase.id, admin.id, "note")


def test_failed_purchase_still_credited_by_later_paypal_completion(db_session, paypal, people):
    from app.services import billing_service

    buyer, admin = people
    purchase = _purchase(db_session, buyer)
    paypal["order"] = _order(status="CREATED", capture_status=None)
    admin_payments_service.mark_failed(db_session, purchase.id, admin.id, "abandoned")
    db_session.commit()

    billing_service.handle_webhook_event(db_session, {
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"id": "CAP-LATE", "status": "COMPLETED", "amount": {"value": "10.00", "currency_code": "USD"},
                     "supplementary_data": {"related_ids": {"order_id": purchase.paypal_order_id}}},
    })

    assert purchase.status == "completed"
    assert _balance(db_session, buyer) == 10


# --- list / detail ----------------------------------------------------------------


def test_list_hides_test_purchases_unless_asked(db_session, people):
    buyer, _ = people
    _purchase(db_session, buyer, source="paypal")
    _purchase(db_session, buyer, source="mock")
    _purchase(db_session, buyer, source="manual_admin", status="completed")

    default = admin_payments_service.list_purchases(db_session)
    with_mock = admin_payments_service.list_purchases(db_session, include_mock=True)
    only_mock = admin_payments_service.list_purchases(db_session, source="mock")  # explicit source wins

    assert sorted(v.purchase.source for v in default.items) == ["manual_admin", "paypal"]
    assert default.total == 2
    assert with_mock.total == 3
    assert [v.purchase.source for v in only_mock.items] == ["mock"]


def test_list_filters_by_email_and_status(db_session, people):
    buyer, admin = people
    _purchase(db_session, buyer, status="pending")
    _purchase(db_session, buyer, status="completed")
    _purchase(db_session, admin, status="pending")

    result = admin_payments_service.list_purchases(db_session, email="BUYER@", status="pending")

    assert result.total == 1
    assert result.items[0].user_email == "buyer@example.com"


def test_detail_flags_follow_status(db_session, paypal, people):
    buyer, admin = people
    old_pending = _purchase(db_session, buyer)
    new_pending = _purchase(db_session, buyer, created_at=datetime.now(timezone.utc))
    refunded = _refunded(db_session, buyer)
    manual = _purchase(db_session, buyer, source="manual_admin", status="completed")

    d = admin_payments_service.get_purchase_detail
    assert (d(db_session, old_pending.id).can_recheck, d(db_session, old_pending.id).can_mark_failed) == (True, True)
    assert d(db_session, new_pending.id).can_mark_failed is False
    assert d(db_session, refunded.id).can_take_back is True
    assert d(db_session, manual.id).can_recheck is False

    admin_payments_service.take_back_credits(db_session, refunded.id, admin.id, "refund")
    db_session.commit()
    after = d(db_session, refunded.id)
    assert after.can_take_back is False
    assert after.credits_taken_back == 10
    assert after.view.resolved_by_email == "admin@example.com"
    assert sorted(t.amount for t in after.ledger) == [-10, 10]


def test_detail_unknown_purchase_raises(db_session):
    with pytest.raises(admin_payments_service.PurchaseNotFoundError):
        admin_payments_service.get_purchase_detail(db_session, uuid.uuid4())


def test_payments_status_reports_mode_without_secrets(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_ID", "id")
    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_SECRET", "secret")
    monkeypatch.setenv("REDOWEBS_PAYPAL_ENV", "live")
    monkeypatch.setenv("REDOWEBS_PAYPAL_WEBHOOK_ID", "")
    get_settings.cache_clear()

    status = admin_payments_service.payments_status()

    assert status.mode == "paypal_live"
    assert status.paypal_configured is True
    assert status.webhook_configured is False
    assert "secret" not in str(status.__dict__)

    monkeypatch.setenv("REDOWEBS_PAYMENTS_MODE", "mock")
    monkeypatch.setenv("REDOWEBS_FRONTEND_URL", "https://redowebs.example.com")
    get_settings.cache_clear()
    assert admin_payments_service.payments_status().mock_requested_but_ignored is True
