import types
import uuid
from datetime import datetime, timezone

from app.config import get_settings
from app.services import model_config_service


class _FakeTierRow:
    def __init__(self, key, generation_model):
        self.key = key
        self.label = key
        self.is_active = True
        self.sort_order = 1
        self.download_credit_cost = 1
        self.generation_model = generation_model
        self.updated_at = datetime.now(timezone.utc)
        self.updated_by_admin_id = None


class _FakeSessionForTier:
    def __init__(self, row):
        self._row = row

    def scalar(self, _query):
        return self._row


class _FakeSessionForAISetting:
    def __init__(self, row):
        self._row = row

    def get(self, _model, _key):
        return self._row


def test_get_generation_model_uses_tier_override_when_set():
    db = _FakeSessionForTier(_FakeTierRow("pro", "anthropic/claude-opus-5"))

    assert model_config_service.get_generation_model("pro", db) == "anthropic/claude-opus-5"


def test_get_generation_model_falls_back_to_config_default_when_tier_has_no_override():
    db = _FakeSessionForTier(_FakeTierRow("pro", None))

    assert model_config_service.get_generation_model("pro", db) == get_settings().generation_model


def test_get_generation_model_falls_back_to_config_default_when_tier_missing():
    db = _FakeSessionForTier(None)

    assert model_config_service.get_generation_model("unknown-tier", db) == get_settings().generation_model


def test_get_vision_model_uses_db_override_when_present():
    row = types.SimpleNamespace(model_name="anthropic/claude-opus-5")
    db = _FakeSessionForAISetting(row)

    assert model_config_service.get_vision_model(db) == "anthropic/claude-opus-5"


def test_get_vision_model_falls_back_to_config_default_when_no_row():
    db = _FakeSessionForAISetting(None)

    assert model_config_service.get_vision_model(db) == get_settings().vision_model


def _make_admin(db_session):
    from app.models import User

    admin = User(email="model-config-admin@example.com", is_email_verified=True, is_admin=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_set_vision_model_creates_row_when_missing(db_session):
    admin = _make_admin(db_session)

    setting = model_config_service.set_vision_model("openai/gpt-4o-mini", admin.id, db_session)
    db_session.commit()

    assert setting.model_name == "openai/gpt-4o-mini"
    assert setting.updated_by_admin_id == admin.id
    assert model_config_service.get_vision_model(db_session) == "openai/gpt-4o-mini"


def test_set_vision_model_updates_existing_row(db_session):
    admin = _make_admin(db_session)
    model_config_service.set_vision_model("openai/gpt-4o-mini", admin.id, db_session)
    db_session.commit()

    model_config_service.set_vision_model("anthropic/claude-opus-5", admin.id, db_session)
    db_session.commit()

    from app.models import AIModelSetting

    rows = db_session.query(AIModelSetting).filter(AIModelSetting.key == "vision_model").all()
    assert len(rows) == 1
    assert rows[0].model_name == "anthropic/claude-opus-5"
