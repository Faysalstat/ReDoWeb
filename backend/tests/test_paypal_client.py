import httpx
import pytest

from app.config import get_settings
from app.payments import paypal_client
from app.payments.paypal_client import PayPalError, PayPalNotConfiguredError

SANDBOX = "https://api-m.sandbox.paypal.com"


@pytest.fixture(autouse=True)
def _paypal_settings(monkeypatch):
    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_ID", "client-id")
    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("REDOWEBS_PAYPAL_ENV", "sandbox")
    monkeypatch.setenv("REDOWEBS_PAYPAL_WEBHOOK_ID", "WH-1")
    get_settings.cache_clear()
    paypal_client._clear_token_cache()
    yield
    paypal_client._clear_token_cache()
    get_settings.cache_clear()


def _response(status_code: int, payload: dict | None = None, method="POST", url=SANDBOX) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request(method, url))


class _FakeHttp:
    """Scripted httpx.post/httpx.get: token requests always succeed (and
    are counted); everything else pops from `responses`."""

    def __init__(self, monkeypatch, responses):
        self.responses = list(responses)
        self.token_calls = 0
        self.calls = []
        monkeypatch.setattr(httpx, "post", self._post)
        monkeypatch.setattr(httpx, "get", self._get)

    def _next(self, method, url, kwargs):
        if url.endswith("/v1/oauth2/token"):
            self.token_calls += 1
            return _response(200, {"access_token": f"tok-{self.token_calls}", "expires_in": 32400})
        self.calls.append({"method": method, "url": url, **kwargs})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def _post(self, url, **kwargs):
        return self._next("POST", url, kwargs)

    def _get(self, url, **kwargs):
        return self._next("GET", url, kwargs)


def test_create_order_sends_exact_amount_and_request_id(monkeypatch):
    http = _FakeHttp(monkeypatch, [_response(201, {"id": "ORDER-1"})])

    order_id = paypal_client.create_order(purchase_id="p-1", amount_cents=4500, description="50 credits")

    assert order_id == "ORDER-1"
    call = http.calls[0]
    assert call["url"] == f"{SANDBOX}/v2/checkout/orders"
    unit = call["json"]["purchase_units"][0]
    assert unit["amount"] == {"currency_code": "USD", "value": "45.00"}
    assert unit["custom_id"] == "p-1"
    assert call["json"]["intent"] == "CAPTURE"
    assert call["headers"]["PayPal-Request-Id"] == "create-p-1"
    assert call["headers"]["Authorization"] == "Bearer tok-1"


def test_access_token_is_cached_across_calls(monkeypatch):
    http = _FakeHttp(monkeypatch, [_response(201, {"id": "O1"}), _response(201, {"id": "O2"})])

    paypal_client.create_order(purchase_id="a", amount_cents=100, description="x")
    paypal_client.create_order(purchase_id="b", amount_cents=100, description="x")

    assert http.token_calls == 1


def test_401_refreshes_token_once_and_retries(monkeypatch):
    http = _FakeHttp(monkeypatch, [_response(401, {}), _response(200, {"id": "ORDER-1", "status": "COMPLETED"})])

    paypal_client.capture_order("ORDER-1")

    assert http.token_calls == 2
    assert http.calls[1]["headers"]["Authorization"] == "Bearer tok-2"
    assert http.calls[1]["headers"]["PayPal-Request-Id"] == "capture-ORDER-1"


def test_already_captured_is_surfaced_as_issue(monkeypatch):
    _FakeHttp(
        monkeypatch,
        [_response(422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_ALREADY_CAPTURED"}]})],
    )

    with pytest.raises(PayPalError) as exc_info:
        paypal_client.capture_order("ORDER-1")

    assert exc_info.value.issue == "ORDER_ALREADY_CAPTURED"
    assert exc_info.value.transient is False


def test_timeout_is_transient(monkeypatch):
    _FakeHttp(monkeypatch, [httpx.ReadTimeout("slow")])

    with pytest.raises(PayPalError) as exc_info:
        paypal_client.capture_order("ORDER-1")

    assert exc_info.value.transient is True


def test_server_error_is_transient(monkeypatch):
    _FakeHttp(monkeypatch, [_response(503, {"name": "SERVICE_UNAVAILABLE"})])

    with pytest.raises(PayPalError) as exc_info:
        paypal_client.capture_order("ORDER-1")

    assert exc_info.value.transient is True


def test_not_configured_raises(monkeypatch):
    monkeypatch.setenv("REDOWEBS_PAYPAL_CLIENT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(PayPalNotConfiguredError):
        paypal_client.capture_order("ORDER-1")


_SIG_HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
    "PAYPAL-TRANSMISSION-ID": "t-1",
    "PAYPAL-TRANSMISSION-SIG": "sig",
    "PAYPAL-TRANSMISSION-TIME": "2026-10-05T00:00:00Z",
}


def test_verify_webhook_signature_success(monkeypatch):
    http = _FakeHttp(monkeypatch, [_response(200, {"verification_status": "SUCCESS"})])
    event = {"id": "WH-EVT-1", "event_type": "PAYMENT.CAPTURE.COMPLETED"}

    assert paypal_client.verify_webhook_signature(_SIG_HEADERS, event) is True
    body = http.calls[0]["json"]
    assert body["webhook_id"] == "WH-1"
    assert body["webhook_event"] == event
    assert body["transmission_id"] == "t-1"


def test_verify_webhook_signature_failure(monkeypatch):
    _FakeHttp(monkeypatch, [_response(200, {"verification_status": "FAILURE"})])

    assert paypal_client.verify_webhook_signature(_SIG_HEADERS, {"id": "x"}) is False


def test_verify_webhook_signature_rejects_missing_headers_without_calling_paypal(monkeypatch):
    http = _FakeHttp(monkeypatch, [])

    assert paypal_client.verify_webhook_signature({"paypal-auth-algo": "x"}, {"id": "x"}) is False
    assert http.calls == []


def test_verify_webhook_signature_rejects_when_webhook_id_unset(monkeypatch):
    monkeypatch.setenv("REDOWEBS_PAYPAL_WEBHOOK_ID", "")
    get_settings.cache_clear()
    http = _FakeHttp(monkeypatch, [])

    assert paypal_client.verify_webhook_signature(_SIG_HEADERS, {"id": "x"}) is False
    assert http.calls == []


@pytest.mark.parametrize("cents,expected", [(1000, "10.00"), (99, "0.99"), (4505, "45.05"), (0, "0.00")])
def test_format_amount(cents, expected):
    assert paypal_client.format_amount(cents) == expected
