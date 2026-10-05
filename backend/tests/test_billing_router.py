"""HTTP-level checks for routers/billing.py and routers/tiers.py: the
webhook's signature gate, public-vs-login access, and ownership 404s.
Uses its own thread-safe SQLite engine (TestClient runs sync handlers in a
worker thread, which the shared in-memory db_session fixture can't serve)."""

import types
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import CreditPack, CreditTransaction, CreditWallet, Purchase, Tier, User
from app.payments import paypal_client


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            CreditWallet.__table__,
            CreditTransaction.__table__,
            CreditPack.__table__,
            Purchase.__table__,
            Tier.__table__,
        ],
    )
    factory = sessionmaker(bind=engine)

    def _get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    yield factory
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(session_factory):
    return TestClient(app)


def _seed(factory):
    with factory() as db:
        user = User(email="buyer@example.com", is_email_verified=True)
        other = User(email="other@example.com", is_email_verified=True)
        db.add_all([user, other])
        db.add(CreditPack(id=uuid.uuid4(), name="Starter", credits=10, price_usd_cents=1000, is_active=True, sort_order=1))
        db.add(CreditPack(id=uuid.uuid4(), name="Hidden", credits=99, price_usd_cents=1, is_active=False, sort_order=2))
        db.add(Tier(id=uuid.uuid4(), key="pro", label="Pro", is_active=True, sort_order=1, download_credit_cost=10))
        db.add(Tier(id=uuid.uuid4(), key="basic", label="Basic", is_active=False, sort_order=0, download_credit_cost=3))
        db.commit()
        db.add(
            Purchase(
                user_id=user.id, amount_usd_cents=1000, credits_granted=10, status="pending", source="paypal",
                paypal_order_id="ORDER-1",
            )
        )
        db.commit()
        return user.id, other.id


def _login_as(user_id):
    app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(id=user_id, is_admin=False)


@pytest.fixture(autouse=True)
def _clear_user_override():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_credit_packs_are_public_and_only_active(client, session_factory):
    _seed(session_factory)

    response = client.get("/api/v1/billing/credit-packs")

    assert response.status_code == 200
    assert [p["name"] for p in response.json()["items"]] == ["Starter"]


def test_tiers_are_public_and_only_active(client, session_factory):
    _seed(session_factory)

    response = client.get("/api/v1/tiers")

    assert response.status_code == 200
    assert response.json()["items"] == [{"key": "pro", "label": "Pro", "download_credit_cost": 10}]


def test_billing_config_is_public_and_reports_disabled_without_credentials(client):
    response = client.get("/api/v1/billing/config")

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["currency"] == "USD"


def test_create_order_requires_login(client, session_factory):
    _seed(session_factory)

    response = client.post("/api/v1/billing/paypal/orders", json={"pack_id": str(uuid.uuid4())})

    assert response.status_code == 401


def test_capture_of_someone_elses_order_is_404(client, session_factory, monkeypatch):
    _, other_id = _seed(session_factory)
    _login_as(other_id)
    monkeypatch.setattr(paypal_client, "capture_order", lambda order_id: pytest.fail("must not call PayPal"))

    response = client.post("/api/v1/billing/paypal/orders/ORDER-1/capture")

    assert response.status_code == 404


def test_webhook_with_invalid_signature_is_rejected_and_grants_nothing(client, session_factory, monkeypatch):
    _seed(session_factory)
    monkeypatch.setattr(paypal_client, "verify_webhook_signature", lambda headers, event: False)
    monkeypatch.setattr(paypal_client, "capture_order", lambda order_id: pytest.fail("must not capture"))

    response = client.post(
        "/api/v1/billing/paypal/webhook",
        json={"event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": "ORDER-1"}},
    )

    assert response.status_code == 400
    with session_factory() as db:
        assert db.query(CreditTransaction).count() == 0
        assert db.query(Purchase).one().status == "pending"


def test_webhook_verification_outage_returns_503_so_paypal_retries(client, session_factory, monkeypatch):
    _seed(session_factory)

    def _down(headers, event):
        raise paypal_client.PayPalError("down", transient=True)

    monkeypatch.setattr(paypal_client, "verify_webhook_signature", _down)

    response = client.post("/api/v1/billing/paypal/webhook", json={"event_type": "X"})

    assert response.status_code == 503


def test_verified_webhook_fulfils_purchase(client, session_factory, monkeypatch):
    user_id, _ = _seed(session_factory)
    monkeypatch.setattr(paypal_client, "verify_webhook_signature", lambda headers, event: True)

    response = client.post(
        "/api/v1/billing/paypal/webhook",
        json={
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAP-1",
                "status": "COMPLETED",
                "amount": {"value": "10.00", "currency_code": "USD"},
                "supplementary_data": {"related_ids": {"order_id": "ORDER-1"}},
            },
        },
    )

    assert response.status_code == 200
    with session_factory() as db:
        assert db.query(Purchase).one().status == "completed"
        assert db.query(CreditWallet).filter(CreditWallet.user_id == user_id).one().balance == 10
