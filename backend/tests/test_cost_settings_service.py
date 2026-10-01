import types

from app.config import get_settings
from app.services import cost_settings_service


class _FakeSessionForCostSetting:
    def __init__(self, row):
        self._row = row

    def get(self, _model, _key):
        return self._row


def test_get_generation_cost_alert_usd_uses_db_override_when_present():
    row = types.SimpleNamespace(value=2.5)
    db = _FakeSessionForCostSetting(row)

    assert cost_settings_service.get_generation_cost_alert_usd(db) == 2.5


def test_get_generation_cost_alert_usd_falls_back_to_config_default_when_no_row():
    db = _FakeSessionForCostSetting(None)

    assert (
        cost_settings_service.get_generation_cost_alert_usd(db)
        == get_settings().generation_cost_alert_usd_default
    )


def test_get_usd_per_credit_uses_db_override_when_present():
    row = types.SimpleNamespace(value=0.5)
    db = _FakeSessionForCostSetting(row)

    assert cost_settings_service.get_usd_per_credit(db) == 0.5


def test_get_usd_per_credit_falls_back_to_config_default_when_no_row():
    db = _FakeSessionForCostSetting(None)

    assert cost_settings_service.get_usd_per_credit(db) == get_settings().usd_per_credit_default


def _make_admin(db_session):
    from app.models import User

    admin = User(email="cost-settings-admin@example.com", is_email_verified=True, is_admin=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_set_generation_cost_alert_usd_creates_row_when_missing(db_session):
    admin = _make_admin(db_session)

    cost_settings_service.set_generation_cost_alert_usd(3.0, admin.id, db_session)
    db_session.commit()

    assert cost_settings_service.get_generation_cost_alert_usd(db_session) == 3.0


def test_set_generation_cost_alert_usd_updates_existing_row(db_session):
    admin = _make_admin(db_session)
    cost_settings_service.set_generation_cost_alert_usd(3.0, admin.id, db_session)
    db_session.commit()

    cost_settings_service.set_generation_cost_alert_usd(4.5, admin.id, db_session)
    db_session.commit()

    from app.models import CostSetting

    rows = (
        db_session.query(CostSetting)
        .filter(CostSetting.key == cost_settings_service.GENERATION_COST_ALERT_USD_KEY)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].value == 4.5


def test_set_usd_per_credit_creates_row_when_missing(db_session):
    admin = _make_admin(db_session)

    cost_settings_service.set_usd_per_credit(0.75, admin.id, db_session)
    db_session.commit()

    assert cost_settings_service.get_usd_per_credit(db_session) == 0.75


def test_set_usd_per_credit_updates_existing_row(db_session):
    admin = _make_admin(db_session)
    cost_settings_service.set_usd_per_credit(0.75, admin.id, db_session)
    db_session.commit()

    cost_settings_service.set_usd_per_credit(1.25, admin.id, db_session)
    db_session.commit()

    from app.models import CostSetting

    rows = (
        db_session.query(CostSetting)
        .filter(CostSetting.key == cost_settings_service.USD_PER_CREDIT_KEY)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].value == 1.25
