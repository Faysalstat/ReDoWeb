import httpx
import pytest

from app.crawler.errors import SiteInaccessible
from app.crawler.robots import check_robots_allowed

UA = "ReDoWebsBot/0.1 (+https://redowebs.example/bot)"
START_URL = "https://example.com/"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_allows_when_robots_txt_allows_homepage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="User-Agent: *\nAllow: /\nDisallow: /search\n")

    with _client(handler) as client:
        check_robots_allowed(client, START_URL, UA)  # no raise


def test_rejects_when_robots_txt_disallows_homepage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="User-Agent: *\nDisallow: /\n")

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible):
            check_robots_allowed(client, START_URL, UA)


def test_missing_robots_txt_is_treated_as_allow_all():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with _client(handler) as client:
        check_robots_allowed(client, START_URL, UA)  # no raise


def test_unreachable_robots_txt_is_treated_as_allow_all():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with _client(handler) as client:
        check_robots_allowed(client, START_URL, UA)  # no raise


def test_403_on_robots_txt_fetch_itself_is_rejected():
    """A real bot-block on the robots.txt request itself (not just a rule
    inside it) is still treated as disallowed -- distinct from the bug this
    module fixes, where a *different*, unauthenticated User-Agent used to
    be the one making this request and could get 403'd even when our real
    crawler UA would've been let through and allowed by the actual rules."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    with _client(handler) as client:
        with pytest.raises(SiteInaccessible):
            check_robots_allowed(client, START_URL, UA)
