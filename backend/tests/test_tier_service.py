import uuid

import pytest

from app.models import Tier as TierORM
from app.models import User
from app.services import tier_service


def _make_admin(db_session) -> User:
    admin = User(email="tier-admin@example.com", is_email_verified=True, is_admin=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _make_tier(db_session, key="pro") -> TierORM:
    tier = TierORM(id=uuid.uuid4(), key=key, label=key.title(), is_active=True, sort_order=1, download_credit_cost=10)
    db_session.add(tier)
    db_session.commit()
    return tier


def test_set_generation_model_sets_override_and_audit(db_session):
    admin = _make_admin(db_session)
    _make_tier(db_session)

    result = tier_service.set_generation_model("pro", "anthropic/claude-opus-5", admin.id, db_session)
    db_session.commit()

    assert result.generation_model == "anthropic/claude-opus-5"
    assert result.updated_by_admin_id == admin.id

    fetched = tier_service.get_tier("pro", db_session)
    assert fetched.generation_model == "anthropic/claude-opus-5"


def test_set_generation_model_none_clears_override(db_session):
    admin = _make_admin(db_session)
    _make_tier(db_session)
    tier_service.set_generation_model("pro", "anthropic/claude-opus-5", admin.id, db_session)
    db_session.commit()

    tier_service.set_generation_model("pro", None, admin.id, db_session)
    db_session.commit()

    fetched = tier_service.get_tier("pro", db_session)
    assert fetched.generation_model is None


def test_set_generation_model_raises_for_unknown_key(db_session):
    admin = _make_admin(db_session)

    with pytest.raises(ValueError):
        tier_service.set_generation_model("nonexistent", "openai/gpt-4o-mini", admin.id, db_session)


def test_set_active_disables_and_enables_tier(db_session):
    admin = _make_admin(db_session)
    _make_tier(db_session)

    result = tier_service.set_active("pro", False, admin.id, db_session)
    db_session.commit()

    assert result.is_active is False
    assert result.updated_by_admin_id == admin.id
    assert tier_service.is_tier_enabled("pro", db_session) is False

    tier_service.set_active("pro", True, admin.id, db_session)
    db_session.commit()

    assert tier_service.is_tier_enabled("pro", db_session) is True


def test_set_active_raises_for_unknown_key(db_session):
    admin = _make_admin(db_session)

    with pytest.raises(ValueError):
        tier_service.set_active("nonexistent", False, admin.id, db_session)


def test_update_tier_sets_label_order_and_cost(db_session):
    admin = _make_admin(db_session)
    _make_tier(db_session)

    result = tier_service.update_tier(
        "pro", label="  Pro Max  ", sort_order=5, download_credit_cost=12, admin_id=admin.id, db=db_session
    )

    assert (result.key, result.label, result.sort_order, result.download_credit_cost) == ("pro", "Pro Max", 5, 12)
    assert result.updated_by_admin_id == admin.id


@pytest.mark.parametrize(
    "label,cost",
    [("", 5), ("   ", 5), ("x" * 65, 5), ("Pro", 0)],
)
def test_update_tier_rejects_invalid_values(db_session, label, cost):
    admin = _make_admin(db_session)
    _make_tier(db_session)

    with pytest.raises(ValueError):
        tier_service.update_tier("pro", label=label, sort_order=1, download_credit_cost=cost, admin_id=admin.id, db=db_session)


def test_update_tier_unknown_key_raises_lookup_error(db_session):
    admin = _make_admin(db_session)

    with pytest.raises(LookupError):
        tier_service.update_tier("nope", label="X", sort_order=1, download_credit_cost=5, admin_id=admin.id, db=db_session)
