import httpx
import pytest

from app.crawler.errors import SiteInaccessible
from app.crawler.fetch import fetch_page

URL = "https://example.com/"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_200_returns_the_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>")

    with _client(handler) as client:
        response = fetch_page(client, URL)
        assert response.status_code == 200


@pytest.mark.parametrize("status", [401, 403])
def test_403_raises_a_bot_protection_message_not_a_raw_status(status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible) as exc_info:
            fetch_page(client, URL)
    message = str(exc_info.value)
    assert "bot-protection" in message
    assert str(status) not in message  # not a bare "HTTP 403" dump


def test_404_raises_a_not_found_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible, match="could not be found"):
            fetch_page(client, URL)


def test_500_raises_a_server_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible, match="server returned an error"):
            fetch_page(client, URL)


def test_connect_error_raises_a_friendly_message_not_the_raw_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[Errno 11001] getaddrinfo failed", request=request)

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible) as exc_info:
            fetch_page(client, URL)
    assert "getaddrinfo" not in str(exc_info.value)
    assert "double-check the URL" in str(exc_info.value)


def test_timeout_raises_a_friendly_message():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible, match="took too long to respond"):
            fetch_page(client, URL)


def test_login_wall_is_detected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='<html><input type="password"></html>')

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible, match="require a login"):
            fetch_page(client, "https://example.com/login")
