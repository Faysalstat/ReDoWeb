import json
import uuid
from pathlib import Path

import httpx

from ..config import get_settings
from ..crawler.assets import download_assets, extract_asset_urls
from ..crawler.discover import discover_pages
from ..crawler.robots import check_robots_allowed


def run_crawl(project_id: uuid.UUID, url: str) -> dict:
    """Synchronously crawls `url` (homepage + same-origin nav pages, capped
    at settings.max_pages) and writes the result to
    {storage_root}/projects/{project_id}/snapshot/. Raises CrawlError
    subclasses (SiteInaccessible, CrawlRejected) on definitive failures --
    callers are expected to map these to a 422 response, not retry them.

    `project_id` is assigned by the caller (the router, backed by a Project
    row) rather than generated here, so the DB row and the storage folder
    share the same id. `metadata.json` is still written as-is -- the
    blueprint extractor and site generator read it directly rather than
    querying the DB, so this stays the single source of truth for crawl
    content even though the router now also persists a queryable copy.
    """
    settings = get_settings()
    project_id = str(project_id)
    project_root = Path(settings.storage_root) / "projects" / project_id
    snapshot_root = project_root / "snapshot"
    pages_dir = snapshot_root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(
        headers={"User-Agent": settings.crawler_user_agent},
        timeout=settings.request_timeout_seconds,
    ) as client:
        check_robots_allowed(client, url, settings.crawler_user_agent)
        pages = discover_pages(client, url, settings.max_pages)

        all_assets: list[dict] = []
        page_records: list[dict] = []

        for index, (page_url, response) in enumerate(pages.items()):
            slug = "index" if index == 0 else f"page-{index}"
            html_path = pages_dir / f"{slug}.html"
            html_path.write_text(response.text, encoding="utf-8")

            asset_urls = extract_asset_urls(page_url, response.text)
            all_assets.extend(download_assets(client, asset_urls, snapshot_root))

            page_records.append(
                {
                    "url": page_url,
                    "http_status": response.status_code,
                    "storage_path": html_path.relative_to(project_root).as_posix(),
                }
            )

    unique_assets = list({a["storage_path"]: a for a in all_assets}.values())

    metadata = {
        "project_id": project_id,
        "source_url": url,
        "page_count": len(page_records),
        "pages": page_records,
        "assets": unique_assets,
    }
    (project_root / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    return metadata
