"""Masks secrets before a log line leaves the process (stdout, Axiom, Sentry).
Applied to the message, the traceback and every extra field, so a careless
`logger.info("... %s", headers)` can't leak a token."""

import re
from typing import Any

MASK = "[redacted]"

# Field names whose values are always masked, whatever they contain. Anchored
# to the end of the key so "refresh_token"/"set-cookie" match but token
# *counts* ("prompt_tokens", "max_tokens") don't.
_SENSITIVE_KEY = re.compile(
    r"^(?:.*[_-])?(authorization|cookie|password|passwd|secret|token|api[_-]?key|signature)$",
    re.IGNORECASE,
)

_PATTERNS = (
    # JWTs (our access tokens, Google id tokens).
    re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
    # "Bearer <anything>" / "Basic <anything>" header values.
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    # OpenRouter keys.
    re.compile(r"sk-or-[A-Za-z0-9_-]{8,}"),
    # key=value / "key": "value" pairs embedded in free text (query strings,
    # dumped dicts, raw API error bodies).
    re.compile(
        r"(?i)([\"']?(?:access_token|refresh_token|id_token|client_secret|api_key|password|secret)[\"']?\s*[:=]\s*[\"']?)"
        r"[^\"'&\s,}]+"
    ),
)


def redact_text(text: str) -> str:
    if not text:
        return text
    for pattern in _PATTERNS[:-1]:
        text = pattern.sub(MASK, text)
    return _PATTERNS[-1].sub(lambda m: m.group(1) + MASK, text)


def redact_value(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY.search(key) and value not in (None, "", 0):
        return MASK
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(key, v) for v in value]
    return value
