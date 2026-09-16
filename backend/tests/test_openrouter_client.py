import time

import httpx
import pytest

from app.ai.errors import OpenRouterError
from app.ai.openrouter_client import chat_completion, vision_json_chat
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


def test_chat_completion_raises_openrouter_error_past_hard_deadline(monkeypatch):
    """Regression test for a real incident (2026-09-16): a generation call
    hung for 30+ minutes because httpx's own `timeout=` only bounds time
    between individual reads, not total request duration, so a connection
    that never goes fully silent can hang past it with no exception ever
    raised. `_post_with_hard_deadline` must still surface a clear
    OpenRouterError once the hard wall-clock deadline (soft_timeout +
    margin) elapses, even though the underlying call itself never returns."""
    import app.ai.openrouter_client as client_module

    monkeypatch.setattr(client_module, "_HARD_TIMEOUT_MARGIN_SECONDS", 0.2)

    def hangs_forever(*args, **kwargs):
        time.sleep(30)  # far longer than the test's patched hard deadline

    monkeypatch.setattr(httpx, "post", hangs_forever)

    with pytest.raises(OpenRouterError, match="hard.*deadline"):
        chat_completion({"model": "test-model", "messages": []}, timeout=0.1)
