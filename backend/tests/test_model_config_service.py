import types

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
