import httpx
from bs4 import BeautifulSoup

from .errors import SiteInaccessible

LOGIN_WALL_URL_HINTS = ("login", "signin", "sign-in", "log-in")


def fetch_page(client: httpx.Client, url: str) -> httpx.Response:
    """Fetches a single page. Raises SiteInaccessible for non-200 statuses
    or a detected login/auth wall. Transient network errors (timeouts,
    connection failures) are left to bubble up as httpx exceptions so the
    Celery layer (added in a later milestone) can distinguish and retry
    them -- this synchronous slice has no retry logic of its own yet."""
    response = client.get(url, follow_redirects=True, timeout=15.0)

    if response.status_code >= 400:
        raise SiteInaccessible(f"{url} returned HTTP {response.status_code}")

    final_url = str(response.url).lower()
    if any(hint in final_url for hint in LOGIN_WALL_URL_HINTS):
        soup = BeautifulSoup(response.text, "lxml")
        if soup.find("input", {"type": "password"}):
            raise SiteInaccessible(
                f"{url} appears to require authentication (login wall detected)"
            )

    return response
