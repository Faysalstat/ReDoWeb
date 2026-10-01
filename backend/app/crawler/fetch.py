import httpx
from bs4 import BeautifulSoup

from .errors import SiteInaccessible

LOGIN_WALL_URL_HINTS = ("login", "signin", "sign-in", "log-in")


def _status_message(status_code: int) -> str:
    if status_code in (401, 403):
        # The single most common real-world case, confirmed live against
        # bakertilly.com (2026-09-24): the site itself is fine and its
        # robots.txt allows us, but a WAF/bot-management layer (Cloudflare,
        # Akamai, etc.) blocks the request anyway based on signals other
        # than User-Agent (TLS fingerprint, IP reputation) -- not something
        # this crawler can reliably work around, and not a bug on our side.
        return (
            "This site blocked automated access to this page. It may have "
            "bot-protection enabled that prevents crawling, even though "
            "nothing else appears to be wrong with the site."
        )
    if status_code == 404:
        return "This page could not be found. Please double-check the URL and try again."
    if 500 <= status_code < 600:
        return "This site's server returned an error. Please try again later."
    return f"This site returned an unexpected error (HTTP {status_code})."


def fetch_page(client: httpx.Client, url: str) -> httpx.Response:
    """Fetches a single page. Raises SiteInaccessible (with a message safe
    to show directly to the end user -- see app/errors.py) for a network
    failure, non-200 status, or a detected login/auth wall.

    Network-level errors (timeouts, connection failures, DNS failures) used
    to be left to bubble up as raw httpx exceptions "so a future retry
    layer could distinguish and retry them" -- but no retry layer exists at
    any level above this (CLAUDE.md's "no auto-retry" policy), so in
    practice they were only ever caught by tasks_crawl.py's generic
    `except Exception`, which stored the raw exception text (e.g. a bare
    socket/DNS error) directly in Project.rejection_reason for the frontend
    to display verbatim. Wrapping them here doesn't change what happens
    (the project still ends up "failed" either way) -- it only fixes the
    message shown to the user.
    """
    try:
        response = client.get(url, follow_redirects=True, timeout=15.0)
    except httpx.TimeoutException:
        raise SiteInaccessible(f"{url} took too long to respond. Please try again later.") from None
    except httpx.ConnectError:
        raise SiteInaccessible(
            f"Could not connect to {url}. Please double-check the URL and try again."
        ) from None
    except httpx.TooManyRedirects:
        raise SiteInaccessible(f"{url} redirected too many times and could not be loaded.") from None
    except httpx.HTTPError:
        raise SiteInaccessible(f"Could not reach {url}. Please double-check the URL and try again.") from None

    if response.status_code >= 400:
        raise SiteInaccessible(_status_message(response.status_code))

    final_url = str(response.url).lower()
    if any(hint in final_url for hint in LOGIN_WALL_URL_HINTS):
        soup = BeautifulSoup(response.text, "lxml")
        if soup.find("input", {"type": "password"}):
            raise SiteInaccessible(
                "This site appears to require a login and can't be crawled."
            )

    return response
