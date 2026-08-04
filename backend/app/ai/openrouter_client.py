import base64
import io
import json
import mimetypes
from pathlib import Path

import httpx
from PIL import Image

from ..config import get_settings
from .errors import OpenRouterError


def _image_to_data_url(path: Path, max_dimension: int | None = None) -> str:
    """Encodes an image as a base64 data URL, downscaling it first (long
    edge capped at max_dimension) so vision-token cost doesn't scale with
    the original source photo's resolution -- the blueprint extractor only
    needs enough detail to guess colors/fonts/tone, not pixel-level fidelity.
    """
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "application/octet-stream"

    if max_dimension is not None:
        try:
            with Image.open(path) as img:
                if max(img.size) > max_dimension:
                    img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
                    img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
                    buffer = io.BytesIO()
                    save_format = "JPEG" if img.mode == "RGB" else "PNG"
                    img.save(buffer, format=save_format)
                    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                    mime_type = "image/jpeg" if save_format == "JPEG" else "image/png"
                    return f"data:{mime_type};base64,{encoded}"
        except Exception:
            pass  # fall through to sending the original bytes unresized

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
        url = _image_to_data_url(path, max_dimension=settings.vision_max_image_dimension)
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": settings.vision_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": settings.vision_max_tokens,
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
