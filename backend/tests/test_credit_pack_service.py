import uuid

import pytest

from app.models import User
from app.services import credit_pack_service
from app.services.credit_pack_service import CreditPackNotFoundError


def _make_admin(db_session) -> User:
    admin = User(email="pack-admin@example.com", is_email_verified=True, is_admin=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _create(db_session, admin, **overrides):
    fields = dict(name="Starter", credits=10, price_usd_cents=1000, is_active=False, sort_order=1)
    fields.update(overrides)
    pack = credit_pack_service.create(db_session, admin_id=admin.id, **fields)
    db_session.commit()
    return pack


def test_create_trims_name_and_records_admin(db_session):
    admin = _make_admin(db_session)

    pack = _create(db_session, admin, name="  Starter  ")

    assert pack.name == "Starter"
    assert pack.updated_by_admin_id == admin.id
    assert pack.is_active is False


@pytest.mark.parametrize(
    "overrides",
    [{"name": "   "}, {"name": "x" * 65}, {"credits": 0}, {"price_usd_cents": 0}, {"price_usd_cents": -100}],
)
def test_create_rejects_invalid_values(db_session, overrides):
    admin = _make_admin(db_session)

    with pytest.raises(ValueError):
        _create(db_session, admin, **overrides)


def test_update_changes_fields(db_session):
    admin = _make_admin(db_session)
    pack = _create(db_session, admin)

    updated = credit_pack_service.update(
        db_session, pack.id, name="Value", credits=50, price_usd_cents=4500, sort_order=5, admin_id=admin.id
    )
    db_session.commit()

    assert (updated.name, updated.credits, updated.price_usd_cents, updated.sort_order) == ("Value", 50, 4500, 5)


def test_update_unknown_pack_raises_not_found(db_session):
    admin = _make_admin(db_session)

    with pytest.raises(CreditPackNotFoundError):
        credit_pack_service.update(
            db_session, uuid.uuid4(), name="X", credits=1, price_usd_cents=100, sort_order=0, admin_id=admin.id
        )


def test_set_active_toggles(db_session):
    admin = _make_admin(db_session)
    pack = _create(db_session, admin)

    credit_pack_service.set_active(db_session, pack.id, True, admin.id)
    db_session.commit()
    assert pack.is_active is True

    credit_pack_service.set_active(db_session, pack.id, False, admin.id)
    db_session.commit()
    assert pack.is_active is False


def test_list_all_orders_by_sort_order(db_session):
    admin = _make_admin(db_session)
    _create(db_session, admin, name="B", sort_order=2)
    _create(db_session, admin, name="A", sort_order=1)

    assert [p.name for p in credit_pack_service.list_all(db_session)] == ["A", "B"]
