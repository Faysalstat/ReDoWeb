import httpx
import pytest

from app.ai.errors import OpenRouterError
from app.ai.openrouter_client import vision_json_chat
from app.config import get_settings


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


@pytest.fixture(autouse=True)
def _ensure_api_key(monkeypatch):
    monkeypatch.setenv("REDOWEBS_OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_vision_json_chat_raises_openrouter_error_when_content_is_none(monkeypatch):
    """Some models (observed with deepseek/deepseek-v4-pro in production
    use) return content=None instead of JSON text -- e.g. a refusal or a
    reasoning model that put output elsewhere. json.loads(None) raises a
    bare TypeError, not JSONDecodeError, which used to propagate
    uncaught and crash the whole review call instead of degrading
    gracefully like every other OpenRouterError does."""
    fake_response = _FakeResponse(
        {"choices": [{"message": {"content": None}, "finish_reason": "stop"}], "usage": {}}
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: fake_response)

    with pytest.raises(OpenRouterError):
        vision_json_chat("system prompt", "user text", [])


def test_vision_json_chat_raises_openrouter_error_when_content_is_empty_string(monkeypatch):
    fake_response = _FakeResponse(
        {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}], "usage": {}}
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: fake_response)

    with pytest.raises(OpenRouterError):
        vision_json_chat("system prompt", "user text", [])


def test_vision_json_chat_succeeds_with_real_json_content(monkeypatch):
    fake_response = _FakeResponse(
        {
            "choices": [{"message": {"content": '{"site_name": "Acme"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: fake_response)

    parsed, usage = vision_json_chat("system prompt", "user text", [])

    assert parsed == {"site_name": "Acme"}
    assert usage == {"prompt_tokens": 5, "completion_tokens": 3}
