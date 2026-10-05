"""billing_service with the PayPal client faked at the module boundary --
these test our crediting rules (exactly-once, snapshot pricing, mismatch
rejection, race handling), not PayPal itself."""

import uuid

import pytest

from app.models import CreditPack, CreditTransaction, CreditWallet, Purchase, User
from app.payments import paypal_client
from app.payments.paypal_client import PayPalError
from app.services import billing_service


def _make_user(db_session, email="buyer@example.com") -> User:
    user = User(email=email, is_email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


def _make_pack(db_session, credits=10, price_cents=1000, active=True) -> CreditPack:
    pack = CreditPack(
        id=uuid.uuid4(), name="Starter", credits=credits, price_usd_cents=price_cents, is_active=active, sort_order=1
    )
    db_session.add(pack)
    db_session.commit()
    return pack


def _order_payload(capture_id="CAP-1", status="COMPLETED", value="10.00", currency="USD") -> dict:
    return {
        "id": "ORDER-1",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {"id": capture_id, "status": status, "amount": {"value": value, "currency_code": currency}}
                    ]
                }
            }
        ],
    }


@pytest.fixture
def fake_paypal(monkeypatch):
    """Records calls; tests override `capture_result`/`order_result` to
    script PayPal's answers (a dict, or an exception instance to raise)."""
    state = {"created": [], "captures": 0, "capture_result": _order_payload(), "order_result": _order_payload()}

    def create_order(*, purchase_id, amount_cents, description):
        state["created"].append({"purchase_id": purchase_id, "amount_cents": amount_cents})
        return "ORDER-1"

    def _answer(key):
        result = state[key]
        if isinstance(result, Exception):
            raise result
        return result

    def capture_order(order_id):
        state["captures"] += 1
        return _answer("capture_result")

    def get_order(order_id):
        return _answer("order_result")

    monkeypatch.setattr(paypal_client, "create_order", create_order)
    monkeypatch.setattr(paypal_client, "capture_order", capture_order)
    monkeypatch.setattr(paypal_client, "get_order", get_order)
    return state


def _balance(db_session, user) -> int:
    wallet = db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).one_or_none()
    return wallet.balance if wallet else 0


def _purchase_txn_count(db_session) -> int:
    return db_session.query(CreditTransaction).filter(CreditTransaction.reason == "purchase").count()


def _create(db_session, user, pack) -> Purchase:
    purchase = billing_service.create_order(db_session, user.id, pack.id)
    db_session.commit()
    return purchase


# --- create_order --------------------------------------------------------------


def test_create_order_snapshots_pack_and_sends_server_price(db_session, fake_paypal):
    user = _make_user(db_session)
    pack = _make_pack(db_session, credits=10, price_cents=1000)

    purchase = _create(db_session, user, pack)

    assert purchase.status == "pending"
    assert purchase.source == "paypal"
    assert purchase.paypal_order_id == "ORDER-1"
    assert purchase.credits_granted == 10
    assert purchase.amount_usd_cents == 1000
    assert fake_paypal["created"] == [{"purchase_id": str(purchase.id), "amount_cents": 1000}]


def test_price_change_after_order_does_not_affect_open_order(db_session, fake_paypal):
    user = _make_user(db_session)
    pack = _make_pack(db_session, credits=10, price_cents=1000)
    purchase = _create(db_session, user, pack)

    pack.price_usd_cents = 2500
    pack.credits = 99
    db_session.commit()
    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert outcome.status == "completed"
    assert outcome.credits_granted == 10
    assert _balance(db_session, user) == 10
    assert purchase.amount_usd_cents == 1000


def test_create_order_rejects_inactive_pack(db_session, fake_paypal):
    user = _make_user(db_session)
    pack = _make_pack(db_session, active=False)

    with pytest.raises(billing_service.PackNotFoundError):
        billing_service.create_order(db_session, user.id, pack.id)
    assert fake_paypal["created"] == []


def test_create_order_rejects_unknown_pack(db_session, fake_paypal):
    user = _make_user(db_session)

    with pytest.raises(billing_service.PackNotFoundError):
        billing_service.create_order(db_session, user.id, uuid.uuid4())


# --- capture -------------------------------------------------------------------


def test_capture_completed_grants_credits_once(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))

    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert outcome.status == "completed"
    assert purchase.status == "completed"
    assert purchase.paypal_capture_id == "CAP-1"
    assert _balance(db_session, user) == 10
    txn = db_session.query(CreditTransaction).filter(CreditTransaction.reason == "purchase").one()
    assert txn.related_purchase_id == purchase.id
    assert txn.idempotency_key == f"purchase:{purchase.id}"


def test_capturing_twice_does_not_double_grant_or_recall_paypal(db_session, fake_paypal):
    user = _make_user(db_session)
    _create(db_session, user, _make_pack(db_session))

    billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()
    second = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert second.status == "completed"
    assert fake_paypal["captures"] == 1
    assert _balance(db_session, user) == 10
    assert _purchase_txn_count(db_session) == 1


def test_capture_other_users_order_is_not_found(db_session, fake_paypal):
    owner = _make_user(db_session)
    intruder = _make_user(db_session, email="intruder@example.com")
    _create(db_session, owner, _make_pack(db_session))

    with pytest.raises(billing_service.PurchaseNotFoundError):
        billing_service.capture_for_user(db_session, intruder.id, "ORDER-1")
    assert fake_paypal["captures"] == 0


def test_capture_unknown_order_is_not_found(db_session, fake_paypal):
    user = _make_user(db_session)

    with pytest.raises(billing_service.PurchaseNotFoundError):
        billing_service.capture_for_user(db_session, user.id, "NOPE")


@pytest.mark.parametrize(
    "value,currency",
    [("5.00", "USD"), ("10.01", "USD"), ("10.00", "EUR")],
)
def test_amount_or_currency_mismatch_grants_nothing(db_session, fake_paypal, value, currency):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session, price_cents=1000))
    fake_paypal["capture_result"] = _order_payload(value=value, currency=currency)

    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert outcome.status == "failed"
    assert purchase.status == "failed"
    assert purchase.note
    assert _balance(db_session, user) == 0


def test_pending_capture_leaves_purchase_pending(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))
    fake_paypal["capture_result"] = _order_payload(status="PENDING")

    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert outcome.status == "pending"
    assert purchase.status == "pending"
    assert purchase.paypal_capture_id == "CAP-1"
    assert _balance(db_session, user) == 0


def test_already_captured_fetches_order_and_fulfils_once(db_session, fake_paypal):
    """The webhook (or another tab) captured first: PayPal answers 422
    ORDER_ALREADY_CAPTURED, which must be fulfilled, not reported as an
    error."""
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))
    fake_paypal["capture_result"] = PayPalError("already", status_code=422, issue="ORDER_ALREADY_CAPTURED")

    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert outcome.status == "completed"
    assert purchase.status == "completed"
    assert _balance(db_session, user) == 10


def test_capture_timeout_leaves_purchase_pending_without_grant(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))
    fake_paypal["capture_result"] = PayPalError("timed out", transient=True)

    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    assert outcome.status == "pending"
    assert purchase.status == "pending"
    assert _balance(db_session, user) == 0


def test_declined_instrument_reports_failed_but_keeps_order_retryable(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))
    fake_paypal["capture_result"] = PayPalError("declined", status_code=422, issue="INSTRUMENT_DECLINED")

    outcome = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()
    assert outcome.status == "failed"
    assert outcome.reason == "INSTRUMENT_DECLINED"
    assert purchase.status == "pending"

    fake_paypal["capture_result"] = _order_payload()
    retry = billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()
    assert retry.status == "completed"
    assert _balance(db_session, user) == 10


def test_failed_capture_can_still_complete_later(db_session, fake_paypal):
    """A DECLINED capture marks the purchase failed, but a later valid
    COMPLETED capture (buyer retried with another card) must still grant."""
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))
    fake_paypal["capture_result"] = _order_payload(status="DECLINED")
    billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()
    assert purchase.status == "failed"

    event = _capture_event("PAYMENT.CAPTURE.COMPLETED", capture_id="CAP-2")
    billing_service.handle_webhook_event(db_session, event)
    db_session.commit()

    assert purchase.status == "completed"
    assert _balance(db_session, user) == 10


# --- webhooks ------------------------------------------------------------------


def _capture_event(event_type, capture_id="CAP-1", status="COMPLETED", value="10.00", order_id="ORDER-1", custom_id=None):
    resource = {
        "id": capture_id,
        "status": status,
        "amount": {"value": value, "currency_code": "USD"},
        "supplementary_data": {"related_ids": {"order_id": order_id}} if order_id else {},
    }
    if custom_id:
        resource["custom_id"] = custom_id
    return {"event_type": event_type, "resource": resource}


def test_webhook_order_approved_captures_without_user_context(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))

    result = billing_service.handle_webhook_event(
        db_session, {"event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": "ORDER-1"}}
    )
    db_session.commit()

    assert "completed" in result
    assert purchase.status == "completed"
    assert _balance(db_session, user) == 10


def test_capture_then_webhook_grants_once(db_session, fake_paypal):
    user = _make_user(db_session)
    _create(db_session, user, _make_pack(db_session))

    billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()
    billing_service.handle_webhook_event(db_session, _capture_event("PAYMENT.CAPTURE.COMPLETED"))
    billing_service.handle_webhook_event(
        db_session, {"event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": "ORDER-1"}}
    )
    db_session.commit()

    assert _balance(db_session, user) == 10
    assert _purchase_txn_count(db_session) == 1
    assert fake_paypal["captures"] == 1


def test_webhook_capture_completed_falls_back_to_custom_id(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))

    billing_service.handle_webhook_event(
        db_session, _capture_event("PAYMENT.CAPTURE.COMPLETED", order_id=None, custom_id=str(purchase.id))
    )
    db_session.commit()

    assert purchase.status == "completed"
    assert _balance(db_session, user) == 10


def test_webhook_for_unknown_order_is_ignored(db_session, fake_paypal):
    result = billing_service.handle_webhook_event(
        db_session, _capture_event("PAYMENT.CAPTURE.COMPLETED", order_id="UNKNOWN", custom_id="not-a-uuid")
    )

    assert result.startswith("ignored")
    assert _purchase_txn_count(db_session) == 0


def test_refund_webhook_marks_refunded_without_changing_balance(db_session, fake_paypal):
    user = _make_user(db_session)
    purchase = _create(db_session, user, _make_pack(db_session))
    billing_service.capture_for_user(db_session, user.id, "ORDER-1")
    db_session.commit()

    refund_event = {
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "resource": {
            "id": "REFUND-1",
            "links": [{"rel": "up", "href": "https://api-m.sandbox.paypal.com/v2/payments/captures/CAP-1"}],
        },
    }
    billing_service.handle_webhook_event(db_session, refund_event)
    db_session.commit()

    assert purchase.status == "refunded"
    assert _balance(db_session, user) == 10


def test_unhandled_event_type_is_ignored(db_session, fake_paypal):
    assert billing_service.handle_webhook_event(db_session, {"event_type": "BILLING.PLAN.CREATED"}).startswith(
        "ignored"
    )


# --- pure helpers ----------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected", [("10.00", 1000), ("0.99", 99), ("45", 4500), ("10.005", None), ("abc", None), (None, None)]
)
def test_to_cents(value, expected):
    assert billing_service.to_cents(value) == expected


def test_extract_capture_returns_none_before_capture():
    assert billing_service.extract_capture({"id": "ORDER-1", "purchase_units": [{}]}) is None
