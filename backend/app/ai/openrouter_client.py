import base64
import concurrent.futures
import io
import itertools
import json
import mimetypes
from pathlib import Path

import httpx
from PIL import Image

from ..config import get_settings
from .errors import OpenRouterError

_call_counter = itertools.count(1)

# httpx's own `timeout=` bounds the time between individual reads, not the
# request's total duration -- a connection that never goes fully silent for
# a full timeout window (a slow trickle, a stalled-but-alive proxy/provider
# connection) can hang indefinitely past it with no exception ever raised.
# Seen for real: a generation call to moonshotai/kimi-k2.6 hung for 30+
# minutes with the queue worker process alive but stuck -- never timing
# out, never erroring -- leaving the DB job stuck in "running" forever
# (2026-09-16). This margin is added on top of the network-level timeout to
# give httpx's own timeout a chance to fire first (a more specific error),
# while guaranteeing an absolute upper bound either way.
_HARD_TIMEOUT_MARGIN_SECONDS = 30.0


def _post_with_hard_deadline(url: str, headers: dict, json_payload: dict, soft_timeout: float) -> httpx.Response:
    """Runs httpx.post in a worker thread and enforces a hard wall-clock
    deadline via Future.result(timeout=...) that httpx's own `timeout=`
    can't provide (see module comment above). On expiry the abandoned
    thread is NOT forcibly killed -- Python can't do that -- it keeps
    running in the background until httpx's own `soft_timeout` eventually
    resolves it; the caller gets its OpenRouterError back immediately
    regardless, which is what actually matters (the retry/failure-counting
    loop above this can act on it instead of hanging forever)."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(httpx.post, url, headers=headers, json=json_payload, timeout=soft_timeout)
    hard_deadline = soft_timeout + _HARD_TIMEOUT_MARGIN_SECONDS
    try:
        return future.result(timeout=hard_deadline)
    except concurrent.futures.TimeoutError as exc:
        raise OpenRouterError(
            f"OpenRouter request exceeded the hard {hard_deadline:.0f}s deadline with no "
            f"response -- the network layer's own {soft_timeout:.0f}s timeout never fired "
            "(a stalled-but-technically-alive connection), so this deadline exists as a "
            "backstop. The abandoned request may still be running in the background."
        ) from exc
    finally:
        executor.shutdown(wait=False)


def _content_preview(content, limit: int = 300) -> str:
    """Flattens a message's `content` (plain string, or the list-of-blocks
    shape used for cache_control text blocks / vision image_url blocks)
    down to a short single-line preview for console logging.
    """
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        image_count = sum(1 for block in content if isinstance(block, dict) and block.get("type") == "image_url")
        if image_count:
            text += f" [+{image_count} image(s)]"
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
    system_prompt: str, user_text: str, image_paths: list[Path], model: str | None = None
) -> tuple[dict, dict]:
    """Calls the configured OpenRouter vision-capable model with a text
    prompt plus one or more local images, expecting a strict JSON object
    response (via response_format=json_object). Returns (parsed_json, usage).

    Images are inlined as base64 data URLs since they live on local disk,
    not at a publicly reachable URL.

    `model` lets a caller override which model id is used (real callers
    resolve this from the DB-backed model_config_service.get_vision_model()
    once, up front, and thread it down -- see blueprint_pipeline.py); this
    function stays DB-free and falls back to config.py's static
    vision_model default when omitted.
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

    vision_model = model or settings.vision_model
    payload = {
        "model": vision_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": settings.vision_max_tokens,
    }

    call_num = next(_call_counter)
    print(
        f"\n[AI CALL #{call_num}] vision_json_chat -> model={vision_model} "
        f"| images={len(image_paths)}"
    )
    print(f"    system: {_content_preview(system_prompt, 200)}")
    print(f"    user:   {_content_preview(user_text, 300)}")

    try:
        response = _post_with_hard_deadline(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": settings.openrouter_app_name,
            },
            json_payload=payload,
            soft_timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenRouterError(
            f"OpenRouter request failed: {exc} | body: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

    data = response.json()
    try:
        choice = data["choices"][0]
        message_content = choice["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc

    if not isinstance(message_content, str) or not message_content:
        # Some models return content=None (or an empty string) instead of
        # JSON text -- e.g. a refusal, a content filter, or a
        # reasoning-heavy model that put its actual output in a different
        # field and left `content` empty. json.loads(None) raises
        # TypeError, not JSONDecodeError, so this needs its own check
        # rather than falling through to the except below. Surfacing
        # finish_reason is diagnostic here the same way it already is for
        # the generation loop (see site_generator.py's truncation handling).
        raise OpenRouterError(
            f"Model returned no content (finish_reason={choice.get('finish_reason')!r}): {data}"
        )

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
        response = _post_with_hard_deadline(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": settings.openrouter_app_name,
            },
            json_payload=payload,
            soft_timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenRouterError(
            f"OpenRouter request failed: {exc} | body: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

    return response.json()
