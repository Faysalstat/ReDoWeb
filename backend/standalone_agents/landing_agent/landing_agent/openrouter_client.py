import itertools

import httpx

from .config import get_settings
from .errors import OpenRouterError

_call_counter = itertools.count(1)


def _content_preview(content, limit: int = 300) -> str:
    """Flattens a message's `content` (plain string, or the list-of-blocks
    shape used for cache_control text blocks) down to a short single-line
    preview for console logging.
    """
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        text = content or ""
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


def _message_preview(message: dict, limit: int = 300) -> str:
    role = message.get("role", "?")
    parts = []
    content_preview = _content_preview(message.get("content"), limit)
    if content_preview:
        parts.append(content_preview)
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        names = [tc.get("function", {}).get("name") for tc in tool_calls]
        parts.append(f"[tool_calls: {', '.join(names)}]")
    return f"({role}) " + (" | ".join(parts) if parts else "(empty)")


def chat_completion(payload: dict, timeout: float = 180.0) -> dict:
    """Low-level OpenRouter chat-completions call -- returns the raw parsed
    JSON response. The caller inspects `choices[0].message` for tool_calls
    itself rather than expecting a single JSON object back.
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise OpenRouterError(
            "LANDING_AGENT_OPENROUTER_API_KEY is not configured (set it in .env)"
        )

    messages = payload.get("messages") or []
    system_message = next((m for m in messages if m.get("role") == "system"), None)
    latest_message = messages[-1] if messages else None

    call_num = next(_call_counter)
    print(
        f"\n[AI CALL #{call_num}] chat_completion -> model={payload.get('model')} "
        f"| messages_in_context={len(messages)} | tools={len(payload.get('tools') or [])}"
    )
    if system_message is not None:
        print(f"    system: {_content_preview(system_message.get('content'), 200)}")
    if latest_message is not None:
        print(f"    latest: {_message_preview(latest_message, 300)}")

    try:
        response = httpx.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": settings.openrouter_app_name,
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

    return response.json()
