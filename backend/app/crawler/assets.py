import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

FONT_EXTENSIONS = (".woff", ".woff2", ".ttf", ".otf")


def extract_asset_urls(base_url: str, html: str) -> list[tuple[str, str]]:
    """Returns a list of (absolute_url, asset_type) pairs for images, icons,
    and fonts referenced in the page. Best-effort: stylesheet-embedded
    @font-face/background-image URLs are not parsed in this slice."""
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[str, str]] = []

    for tag in soup.find_all("img", src=True):
        found.append((urljoin(base_url, tag["src"]), "image"))

    for tag in soup.find_all("link", href=True):
        rel = tag.get("rel") or []
        href = tag["href"]
        absolute = urljoin(base_url, href)
        if "icon" in rel:
            found.append((absolute, "icon"))
        elif "preload" in rel and tag.get("as") == "font":
            found.append((absolute, "font"))
        elif absolute.lower().endswith(FONT_EXTENSIONS):
            found.append((absolute, "font"))

    return found


def _filename_for(url: str) -> str:
    parsed = urlparse(url)
    original_name = Path(parsed.path).name or "asset"
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"{digest}-{original_name}"


def download_assets(
    client: httpx.Client, asset_urls: list[tuple[str, str]], snapshot_root: Path
) -> list[dict]:
    """Downloads each unique asset URL once into snapshot_root/{asset_type}/.
    Best-effort: an asset that fails to download is skipped rather than
    failing the whole crawl. Returns records with storage_path relative to
    the project root (snapshot_root's parent)."""
    project_root = snapshot_root.parent
    downloaded: list[dict] = []
    seen: set[str] = set()

    for url, asset_type in asset_urls:
        if url in seen:
            continue
        seen.add(url)

        try:
            response = client.get(url, timeout=15.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            continue

        type_dir = snapshot_root / asset_type
        type_dir.mkdir(parents=True, exist_ok=True)
        file_path = type_dir / _filename_for(url)
        file_path.write_bytes(response.content)

        downloaded.append(
            {
                "original_url": url,
                "asset_type": asset_type,
                "storage_path": file_path.relative_to(project_root).as_posix(),
                "content_type": response.headers.get("content-type"),
            }
        )

    return downloaded
