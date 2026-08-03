from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .errors import CrawlRejected
from .fetch import fetch_page

NON_PAGE_SCHEMES = ("mailto:", "tel:", "javascript:")


def _same_origin(base: str, candidate: str) -> bool:
    return urlparse(base).netloc == urlparse(candidate).netloc


def _normalize(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _extract_same_origin_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#") or href.startswith(NON_PAGE_SCHEMES):
            continue
        absolute = urljoin(base_url, href)
        if _same_origin(base_url, absolute):
            links.append(_normalize(absolute))
    return links


def discover_pages(
    client: httpx.Client, start_url: str, max_pages: int
) -> dict[str, httpx.Response]:
    """Breadth-first same-origin page discovery starting from the homepage.

    Raises CrawlRejected as soon as more than `max_pages` distinct pages are
    discovered -- per docs/implementation-plan.md, sites over the page limit
    are rejected outright, not silently truncated to the first N pages.
    """
    start_url = _normalize(start_url)
    visited: dict[str, httpx.Response] = {}
    queued = {start_url}
    frontier = deque([start_url])

    while frontier:
        url = frontier.popleft()
        response = fetch_page(client, url)
        visited[url] = response

        if len(visited) > max_pages:
            raise CrawlRejected(
                f"Site has more than {max_pages} pages; ReDoWebs supports "
                f"sites with up to {max_pages} pages."
            )

        for link in _extract_same_origin_links(url, response.text):
            if link in queued:
                continue
            queued.add(link)
            if len(queued) > max_pages:
                raise CrawlRejected(
                    f"Site has more than {max_pages} pages; ReDoWebs "
                    f"supports sites with up to {max_pages} pages."
                )
            frontier.append(link)

    return visited
