"""Free (no-LLM) brand-color extraction, used by blueprint_extractor.py in
place of asking the vision model to guess colors from images.

Two sources, tried in order:
1. CSS-first: mine color literals out of the crawled homepage's inline
   <style>/style="" content plus its linked stylesheets (fetched on demand,
   not persisted -- the crawler doesn't download .css files today). This is
   the site's real declared brand colors, for free.
2. Pixel fallback: if no usable colors turn up in CSS (e.g. a framework
   with no explicit color declarations), quantize the logo image locally
   and pick its dominant non-neutral colors.

Both stages filter out near-white/near-black/low-saturation "neutral"
colors (typical text/background grays) so what's left is plausible brand
colors rather than page chrome.
"""

import colorsys
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from PIL import Image

from ..config import get_settings

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)")

_SATURATION_FLOOR = 0.15
_LIGHTNESS_FLOOR = 0.08
_LIGHTNESS_CEILING = 0.92


def _normalize_hex(value: str) -> str:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return f"#{value.lower()}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _is_neutral(hex_color: str) -> bool:
    """True for near-white/near-black/low-saturation grays -- the colors
    almost every page uses for text/backgrounds, which drown out the
    actual brand colors if not filtered out."""
    r, g, b = _hex_to_rgb(hex_color)
    _, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return (
        saturation < _SATURATION_FLOOR
        or lightness < _LIGHTNESS_FLOOR
        or lightness > _LIGHTNESS_CEILING
    )


def _palette_to_roles(palette: list[str]) -> dict:
    primary = palette[0]
    secondary = palette[1] if len(palette) > 1 else primary
    accent = palette[2] if len(palette) > 2 else secondary
    return {"primary": primary, "secondary": secondary, "accent": accent}


def gather_css_text(homepage_html: str, homepage_url: str) -> str:
    """Collects inline <style> blocks + style="" attributes from the
    already-crawled homepage HTML, plus a best-effort fetch of its linked
    external stylesheets. Fetch failures are swallowed -- this is a
    best-effort mining pass, not a required data source (extract_colors_from_css
    returning None triggers the pixel fallback)."""
    soup = BeautifulSoup(homepage_html, "lxml")
    chunks = [tag.get_text() for tag in soup.find_all("style")]
    chunks += [tag.get("style", "") for tag in soup.find_all(style=True)]

    stylesheet_urls = [
        urljoin(homepage_url, link["href"])
        for link in soup.find_all("link", href=True)
        if link.get("rel") and "stylesheet" in link.get("rel")
    ]

    if stylesheet_urls:
        settings = get_settings()
        try:
            with httpx.Client(
                headers={"User-Agent": settings.crawler_user_agent},
                timeout=settings.request_timeout_seconds,
                follow_redirects=True,
            ) as client:
                for url in stylesheet_urls[:5]:
                    try:
                        response = client.get(url)
                        if response.status_code == 200:
                            chunks.append(response.text)
                    except httpx.HTTPError:
                        continue
        except Exception:
            pass

    return "\n".join(chunks)


def extract_colors_from_css(css_text: str) -> dict | None:
    """Regex-mines color literals out of raw CSS/HTML text, filters out
    neutrals, and returns the most frequent distinct vivid colors as
    {primary, secondary, accent}. Returns None if nothing usable is found,
    signaling the caller to fall back to pixel-based extraction."""
    counts: dict[str, int] = {}

    for match in _HEX_RE.findall(css_text):
        hex_color = _normalize_hex(match)
        if len(hex_color) == 7:
            counts[hex_color] = counts.get(hex_color, 0) + 1

    for r, g, b in _RGB_RE.findall(css_text):
        try:
            hex_color = _rgb_to_hex(int(r), int(g), int(b))
        except ValueError:
            continue
        counts[hex_color] = counts.get(hex_color, 0) + 1

    vivid = {color: n for color, n in counts.items() if not _is_neutral(color)}
    if not vivid:
        return None

    ranked = sorted(vivid.items(), key=lambda kv: -kv[1])
    return _palette_to_roles([color for color, _ in ranked])


def extract_colors_from_image(image_path: Path, max_colors: int = 8) -> dict | None:
    """Local pixel-based dominant-color fallback (no LLM call) -- quantizes
    the image to a small palette and picks the most common non-neutral
    colors. Used only when CSS mining finds nothing usable."""
    if not image_path.exists():
        return None
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((200, 200))
            quantized = img.quantize(colors=max_colors)
            palette = quantized.getpalette() or []
            color_counts = quantized.getcolors() or []
    except Exception:
        return None

    if not color_counts:
        return None

    color_counts.sort(key=lambda entry: -entry[0])
    vivid = []
    for _, index in color_counts:
        offset = index * 3
        if offset + 3 > len(palette):
            continue
        hex_color = _rgb_to_hex(*palette[offset : offset + 3])
        if not _is_neutral(hex_color):
            vivid.append(hex_color)

    if not vivid:
        return None
    return _palette_to_roles(vivid)
