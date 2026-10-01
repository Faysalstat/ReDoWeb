from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from .errors import SiteInaccessible


def check_robots_allowed(client: httpx.Client, start_url: str, user_agent: str) -> None:
    """Raises SiteInaccessible if robots.txt disallows the crawler on the
    homepage path. Fetches robots.txt ourselves with `client` (the same
    client the rest of the crawl uses, sending our real crawler User-Agent)
    rather than letting `RobotFileParser.read()` do its own fetch --
    `read()` always uses urllib's default "Python-urllib/x.y" User-Agent
    regardless of what's passed to `can_fetch()`, and some sites' bot
    protection 403s that generic UA while happily serving robots.txt (and
    allowing crawling) to a real one. `RobotFileParser.read()` treats any
    401/403 as "disallow all", so that false-positive silently rejected
    sites whose robots.txt actually allows us (confirmed live against
    bakertilly.com, 2026-09-24). A missing/unreachable robots.txt (404,
    timeout, connection error) is still treated as allow-all."""
    robots_url = urljoin(start_url, "/robots.txt")
    try:
        response = client.get(robots_url)
    except httpx.HTTPError:
        return

    if response.status_code == 404:
        return
    if response.status_code in (401, 403):
        raise SiteInaccessible("robots.txt disallows crawling this site")
    if response.status_code >= 400:
        return

    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(user_agent, start_url):
        raise SiteInaccessible("robots.txt disallows crawling this site")
