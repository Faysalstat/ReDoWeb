"""Mock payment mode (payments/mock_gateway.py): every payment succeeds,
but only when running locally, and it still goes through billing_service's
real crediting path."""

import uuid

import httpx
import pytest

from app.config import get_settings
from app.models import CreditPack, CreditTransaction, CreditWallet, Purchase, User
from app.payments import mock_gateway
from app.services import billing_service


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setenv("REDOWEBS_PAYMENTS_MODE", "mock")
    monkeypatch.setenv("REDOWEBS_FRONTEND_URL", "http://localhost:4200")
    get_settings.cache_clear()
    # Any real PayPal call in mock mode is a bug.
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("mock mode must not call PayPal"))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("mock mode must not call PayPal"))
    yield
    get_settings.cache_clear()


def _setup(db_session):
    user = User(email="tester@example.com", is_email_verified=True)
    pack = CreditPack(id=uuid.uuid4(), name="Value", credits=50, price_usd_cents=4500, is_active=True, sort_order=1)
    db_session.add_all([user, pack])
    db_session.commit()
    return user, pack


def test_mock_purchase_grants_credits_without_paypal(db_session, mock_mode):
    user, pack = _setup(db_session)

    purchase = billing_service.create_order(db_session, user.id, pack.id)
    db_session.commit()
    outcome = billing_service.capture_for_user(db_session, user.id, purchase.paypal_order_id)
    db_session.commit()

    assert outcome.status == "completed"
    assert outcome.credits_granted == 50
    assert purchase.source == "mock"
    assert purchase.status == "completed"
    assert purchase.paypal_order_id.startswith("MOCK-")
    assert db_session.query(CreditWallet).filter(CreditWallet.user_id == user.id).one().balance == 50


def test_mock_capture_twice_grants_once(db_session, mock_mode):
    user, pack = _setup(db_session)
    purchase = billing_service.create_order(db_session, user.id, pack.id)
    db_session.commit()

    billing_service.capture_for_user(db_session, user.id, purchase.paypal_order_id)
    billing_service.capture_for_user(db_session, user.id, purchase.paypal_order_id)
    db_session.commit()

    assert db_session.query(CreditTransaction).filter(CreditTransaction.reason == "purchase").count() == 1


def test_mock_mode_ignored_when_frontend_is_not_local(monkeypatch):
    monkeypatch.setenv("REDOWEBS_PAYMENTS_MODE", "mock")
    monkeypatch.setenv("REDOWEBS_FRONTEND_URL", "https://redowebs.example.com")
    get_settings.cache_clear()

    assert mock_gateway.is_requested() is True
    assert mock_gateway.is_active() is False


def test_default_mode_is_real_paypal(monkeypatch):
    monkeypatch.delenv("REDOWEBS_PAYMENTS_MODE", raising=False)
    get_settings.cache_clear()

    assert mock_gateway.is_active() is False


def test_mock_order_round_trips_amount():
    order_id = mock_gateway.create_order(purchase_id=str(uuid.uuid4()), amount_cents=4505, description="x")

    capture = billing_service.extract_capture(mock_gateway.capture_order(order_id))

    assert capture.status == "COMPLETED"
    assert capture.amount_value == "45.05"
    assert capture.currency == "USD"


def test_existing_paypal_purchase_still_uses_paypal_after_switching_to_mock(db_session, mock_mode, monkeypatch):
    """The gateway is chosen per purchase, so a real PayPal order created
    before the mode flip is never "captured" by the mock."""
    user, pack = _setup(db_session)
    db_session.add(
        Purchase(user_id=user.id, amount_usd_cents=4500, credits_granted=50, status="pending", source="paypal",
                 paypal_order_id="REAL-ORDER")
    )
    db_session.commit()
    calls = []
    from app.payments import paypal_client

    monkeypatch.setattr(paypal_client, "capture_order", lambda order_id: calls.append(order_id) or {})

    billing_service.capture_for_user(db_session, user.id, "REAL-ORDER")

    assert calls == ["REAL-ORDER"]
