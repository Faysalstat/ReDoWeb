import base64
import json
import mimetypes
from pathlib import Path

import httpx

from ..config import get_settings
from .errors import OpenRouterError


def _image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def vision_json_chat(
    system_prompt: str, user_text: str, image_paths: list[Path]
) -> tuple[dict, dict]:
    """Calls the configured OpenRouter vision-capable model with a text
    prompt plus one or more local images, expecting a strict JSON object
    response (via response_format=json_object). Returns (parsed_json, usage).

    Images are inlined as base64 data URLs since they live on local disk,
    not at a publicly reachable URL.
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise OpenRouterError(
            "REDOWEBS_OPENROUTER_API_KEY is not configured (set it in backend/.env)"
        )

    content: list[dict] = [{"type": "text", "text": user_text}]
    for path in image_paths:
        content.append({"type": "image_url", "image_url": {"url": _image_to_data_url(path)}})

    payload = {
        "model": settings.vision_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": settings.openrouter_app_name,
            },
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

    data = response.json()
    try:
        message_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc

    try:
        parsed = json.loads(message_content)
    except json.JSONDecodeError as exc:
        raise OpenRouterError(f"Model did not return valid JSON: {message_content}") from exc

    return parsed, data.get("usage", {})


def chat_completion(payload: dict, timeout: float = 120.0) -> dict:
    """Low-level OpenRouter chat-completions call -- returns the raw parsed
    JSON response. Used for the manual tool-calling agent loop, where the
    caller needs to inspect `choices[0].message` for tool_calls itself
    rather than expecting a single JSON object back.
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise OpenRouterError(
            "REDOWEBS_OPENROUTER_API_KEY is not configured (set it in backend/.env)"
        )

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
