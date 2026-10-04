import pytest

from app.crawler import discover
from app.crawler.errors import CrawlRejected


class _FakeResponse:
    def __init__(self, url: str, text: str):
        self.url = url
        self.text = text
        self.status_code = 200


def _make_fetch_page(pages: dict[str, str]):
    def fake_fetch_page(client, url):
        return _FakeResponse(url, pages[url])

    return fake_fetch_page


def _chain_site(num_pages: int) -> dict[str, str]:
    """Builds `num_pages` pages at https://example.com/, /page-1, ..., each
    linking only to the next one in the chain -- BFS discovers exactly one
    new page per fetch, so hitting the page-count cap is deterministic
    regardless of what `max_pages` is (not hardcoded to any one value,
    since the whole point is this is a regression guard for the cap
    itself, not a specific number)."""
    urls = ["https://example.com/"] + [f"https://example.com/page-{i}" for i in range(1, num_pages)]
    pages: dict[str, str] = {}
    for index, url in enumerate(urls):
        next_url = urls[index + 1] if index + 1 < len(urls) else None
        html = f'<html><body><a href="{next_url}">next</a></body></html>' if next_url else "<html><body>end</body></html>"
        pages[url] = html
    return pages


@pytest.mark.parametrize("max_pages", [1, 3, 5, 20])
def test_discover_pages_rejects_exactly_one_page_past_the_limit(monkeypatch, max_pages):
    pages = _chain_site(max_pages + 1)
    monkeypatch.setattr(discover, "fetch_page", _make_fetch_page(pages))

    with pytest.raises(CrawlRejected):
        discover.discover_pages(client=None, start_url="https://example.com/", max_pages=max_pages)


@pytest.mark.parametrize("max_pages", [1, 3, 5, 20])
def test_discover_pages_accepts_exactly_at_the_limit(monkeypatch, max_pages):
    pages = _chain_site(max_pages)
    monkeypatch.setattr(discover, "fetch_page", _make_fetch_page(pages))

    result = discover.discover_pages(client=None, start_url="https://example.com/", max_pages=max_pages)

    assert len(result) == max_pages
