"""HTTP-level checks for routers/admin/payments.py's error mapping: an
action that doesn't apply is a 409, missing PayPal keys a 503, a PayPal
timeout a 502 -- and none of them commit anything."""

import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import CreditPack, CreditTransaction, CreditWallet, Purchase, User
from app.payments import paypal_client
from app.payments.paypal_client import PayPalError

ADMIN_ID = uuid.uuid4()


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, CreditWallet.__table__, CreditTransaction.__table__, CreditPack.__table__, Purchase.__table__],
    )
    make = sessionmaker(bind=engine)

    def _get_db():
        session = make()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(id=ADMIN_ID, is_admin=True, is_active=True)
    yield make
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _purchase(factory, *, status="pending") -> uuid.UUID:
    with factory() as db:
        user = User(email="buyer@example.com", is_email_verified=True)
        db.add(user)
        db.commit()
        purchase = Purchase(
            user_id=user.id, amount_usd_cents=1000, credits_granted=10, status=status, source="paypal",
            paypal_order_id="ORDER-1", created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add(purchase)
        db.commit()
        return purchase.id


def test_take_back_on_pending_purchase_is_409(factory):
    purchase_id = _purchase(factory)

    response = TestClient(app).post(f"/api/v1/admin/purchases/{purchase_id}/take-back", json={"note": "x"})

    assert response.status_code == 409


def test_recheck_without_paypal_keys_is_503(factory, monkeypatch):
    purchase_id = _purchase(factory)
    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_ID", "")
    get_settings.cache_clear()

    response = TestClient(app).post(f"/api/v1/admin/purchases/{purchase_id}/recheck")

    assert response.status_code == 503


def test_recheck_paypal_timeout_is_502_and_changes_nothing(factory, monkeypatch):
    purchase_id = _purchase(factory)

    def _slow(order_id):
        raise PayPalError("slow", transient=True)

    monkeypatch.setattr(paypal_client, "get_order", _slow)

    response = TestClient(app).post(f"/api/v1/admin/purchases/{purchase_id}/recheck")

    assert response.status_code == 502
    with factory() as db:
        purchase = db.get(Purchase, purchase_id)
        assert purchase.status == "pending"
        assert purchase.resolved_at is None


def test_recheck_success_returns_updated_purchase(factory, monkeypatch):
    purchase_id = _purchase(factory)
    monkeypatch.setattr(
        paypal_client,
        "get_order",
        lambda order_id: {
            "status": "COMPLETED",
            "purchase_units": [{"payments": {"captures": [
                {"id": "CAP-1", "status": "COMPLETED", "amount": {"value": "10.00", "currency_code": "USD"}}
            ]}}],
        },
    )

    response = TestClient(app).post(f"/api/v1/admin/purchases/{purchase_id}/recheck")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["purchase"]["status"] == "completed"
    assert body["purchase"]["paypal_capture_id"] == "CAP-1"


def test_mark_failed_requires_note(factory):
    purchase_id = _purchase(factory)

    response = TestClient(app).post(f"/api/v1/admin/purchases/{purchase_id}/mark-failed", json={"note": "  "})

    assert response.status_code == 422


def test_unknown_purchase_is_404(factory):
    response = TestClient(app).get(f"/api/v1/admin/purchases/{uuid.uuid4()}")

    assert response.status_code == 404
