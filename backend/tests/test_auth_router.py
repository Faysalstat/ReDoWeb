from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.routers.auth import GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS, _exchange_code_for_claims
from app.services.auth_service import AuthError


def _mock_token_response(json_body: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = json_body
    return response


def test_exchange_code_for_claims_success():
    fake_claims = {"sub": "google-subject-123", "email": "user@example.com", "email_verified": True}
    with (
        patch("app.routers.auth.httpx.post", return_value=_mock_token_response({"id_token": "fake-id-token"})),
        patch("app.routers.auth.google_id_token.verify_oauth2_token", return_value=fake_claims),
    ):
        claims = _exchange_code_for_claims("fake-code")

    assert claims == fake_claims


def test_exchange_code_for_claims_raises_on_http_error():
    with patch("app.routers.auth.httpx.post", side_effect=httpx.HTTPError("boom")):
        with pytest.raises(AuthError):
            _exchange_code_for_claims("fake-code")


def test_exchange_code_for_claims_raises_when_id_token_missing():
    with patch("app.routers.auth.httpx.post", return_value=_mock_token_response({})):
        with pytest.raises(AuthError):
            _exchange_code_for_claims("fake-code")


def test_exchange_code_for_claims_raises_on_invalid_id_token():
    with (
        patch("app.routers.auth.httpx.post", return_value=_mock_token_response({"id_token": "fake-id-token"})),
        patch("app.routers.auth.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token")),
    ):
        with pytest.raises(AuthError):
            _exchange_code_for_claims("fake-code")


def test_exchange_code_for_claims_allows_clock_skew():
    """A server clock a few seconds behind Google's must not reject a fresh
    id_token as "used too early" -- verification is given a skew allowance."""
    with (
        patch("app.routers.auth.httpx.post", return_value=_mock_token_response({"id_token": "fake-id-token"})),
        patch("app.routers.auth.google_id_token.verify_oauth2_token", return_value={"sub": "x"}) as verify,
    ):
        _exchange_code_for_claims("fake-code")

    assert verify.call_args.kwargs["clock_skew_in_seconds"] == GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS
    assert GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS > 0
