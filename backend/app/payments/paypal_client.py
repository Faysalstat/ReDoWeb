"""Thin PayPal REST client (Orders v2 + webhook verification) over httpx.

Deliberately no PayPal SDK -- this is four calls, and plain httpx matches
how ai/openrouter_client.py talks to its provider (and is mocked the same
way in tests: monkeypatch `httpx.post`/`httpx.get`). Everything that can go
wrong surfaces as one PayPalError so billing_service has a single thing to
catch; `transient` distinguishes "PayPal didn't answer" (timeout/network --
the operation may or may not have happened, so the purchase must stay
pending) from a real rejection.
"""

import threading
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ..config import get_settings

CURRENCY = "USD"

_BASE_URLS = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com",
}

# Refresh the OAuth token a minute before PayPal says it expires, so a
# request never goes out with a token that dies in flight.
_TOKEN_EXPIRY_MARGIN_SECONDS = 60.0

_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}


class PayPalError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        issue: str | None = None,
        transient: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.issue = issue
        self.transient = transient


class PayPalNotConfiguredError(PayPalError):
    """REDOWEBS_PAYPAL_CLIENT_ID/SECRET aren't set -- routers map this to
    503 rather than letting it look like a payment failure."""


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.paypal_client_id and settings.paypal_client_secret)


def base_url() -> str:
    env = get_settings().paypal_env.lower()
    if env not in _BASE_URLS:
        raise PayPalNotConfiguredError(f"REDOWEBS_PAYPAL_ENV must be 'sandbox' or 'live', got {env!r}")
    return _BASE_URLS[env]


def format_amount(cents: int) -> str:
    """PayPal wants a decimal string ("10.00"), never a float."""
    return f"{cents // 100}.{cents % 100:02d}"


def _clear_token_cache() -> None:
    with _token_lock:
        _token_cache["token"] = None
        _token_cache["expires_at"] = 0.0


def get_access_token() -> str:
    """OAuth2 client-credentials token, cached process-wide until shortly
    before it expires (PayPal tokens last ~9 hours)."""
    if not is_configured():
        raise PayPalNotConfiguredError("PayPal is not configured (REDOWEBS_PAYPAL_CLIENT_ID/SECRET)")
    with _token_lock:
        if _token_cache["token"] and time.monotonic() < _token_cache["expires_at"]:
            return _token_cache["token"]
        settings = get_settings()
        try:
            response = httpx.post(
                f"{base_url()}/v1/oauth2/token",
                auth=(settings.paypal_client_id, settings.paypal_client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
                timeout=settings.paypal_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise PayPalError(f"PayPal token request failed: {exc}", transient=True) from exc
        if response.status_code >= 400:
            raise PayPalError(
                f"PayPal token request rejected ({response.status_code})", status_code=response.status_code
            )
        payload = response.json()
        _token_cache["token"] = payload["access_token"]
        _token_cache["expires_at"] = (
            time.monotonic() + float(payload.get("expires_in", 0)) - _TOKEN_EXPIRY_MARGIN_SECONDS
        )
        return _token_cache["token"]


def _error_from_response(response: httpx.Response) -> PayPalError:
    issue = None
    message = f"PayPal returned {response.status_code}"
    try:
        body = response.json()
    except ValueError:
        body = {}
    if isinstance(body, dict):
        details = body.get("details") or []
        if details and isinstance(details[0], dict):
            issue = details[0].get("issue")
        issue = issue or body.get("name")
        if body.get("message"):
            message = f"{message}: {body['message']}"
    return PayPalError(
        message,
        status_code=response.status_code,
        issue=issue,
        # 5xx/429 mean "PayPal didn't process this cleanly" -- treat the
        # same as no answer at all: the caller must not assume failure.
        transient=response.status_code >= 500 or response.status_code == 429,
    )


def _call(method: str, path: str, *, json_body: dict | None = None, request_id: str | None = None) -> dict:
    """One authenticated call. A 401 (token revoked/expired early) clears
    the cache and retries exactly once with a fresh token."""
    settings = get_settings()
    for attempt in range(2):
        headers = {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if request_id:
            # PayPal-side idempotency: replaying the same id returns the
            # original result instead of creating/capturing twice.
            headers["PayPal-Request-Id"] = request_id
        url = f"{base_url()}{path}"
        try:
            if method == "GET":
                response = httpx.get(url, headers=headers, timeout=settings.paypal_timeout_seconds)
            else:
                response = httpx.post(
                    url, headers=headers, json=json_body or {}, timeout=settings.paypal_timeout_seconds
                )
        except httpx.HTTPError as exc:
            raise PayPalError(f"PayPal {method} {path} failed: {exc}", transient=True) from exc
        if response.status_code == 401 and attempt == 0:
            _clear_token_cache()
            continue
        if response.status_code >= 400:
            raise _error_from_response(response)
        return response.json()
    raise PayPalError("PayPal rejected the access token twice", status_code=401)


def create_order(*, purchase_id: str, amount_cents: int, description: str) -> str:
    """Creates a CAPTURE-intent order for exactly `amount_cents` USD and
    returns PayPal's order id. `custom_id` carries our Purchase id so a
    webhook can always find its purchase even without the order id."""
    settings = get_settings()
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": purchase_id,
                "custom_id": purchase_id,
                "description": description[:127],
                "amount": {"currency_code": CURRENCY, "value": format_amount(amount_cents)},
            }
        ],
        "application_context": {
            "brand_name": settings.paypal_brand_name[:127],
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
        },
    }
    order = _call("POST", "/v2/checkout/orders", json_body=body, request_id=f"create-{purchase_id}")
    order_id = order.get("id")
    if not order_id:
        raise PayPalError("PayPal create-order response had no id")
    return order_id


def capture_order(order_id: str) -> dict:
    return _call("POST", f"/v2/checkout/orders/{order_id}/capture", request_id=f"capture-{order_id}")


def get_order(order_id: str) -> dict:
    return _call("GET", f"/v2/checkout/orders/{order_id}")


_SIGNATURE_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}


def verify_webhook_signature(headers: Mapping[str, str], event: dict) -> bool:
    """Asks PayPal whether this webhook delivery is genuine. Returns False
    (never raises) for a missing webhook id or missing signature headers,
    so the router can answer 400 uniformly. `event` must be the parsed body
    exactly as received -- PayPal re-checks it against the signature."""
    webhook_id = get_settings().paypal_webhook_id
    if not webhook_id:
        return False
    lowered = {k.lower(): v for k, v in headers.items()}
    body: dict[str, Any] = {}
    for field, header in _SIGNATURE_HEADERS.items():
        value = lowered.get(header)
        if not value:
            return False
        body[field] = value
    body["webhook_id"] = webhook_id
    body["webhook_event"] = event
    result = _call("POST", "/v1/notifications/verify-webhook-signature", json_body=body)
    return result.get("verification_status") == "SUCCESS"
