"""Deterministic post-processing over the agent's generated HTML output.

The generation agent is instructed to handle SEO/accessibility itself, but
nothing verifies it did. This module is the safety net: fills in any
missing/empty alt text, injects Open Graph tags if absent, runs a
best-effort WCAG AA contrast check against the blueprint's color palette
(flagged only -- never auto-"fixed", since a fix could contradict the
design), and writes sitemap.xml.
"""

import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

FALLBACK_ALT = "Image"


def parse_frontmatter(design_md: str) -> dict:
    if not design_md.startswith("---"):
        return {}
    parts = design_md.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def postprocess_output(output_dir: Path, frontmatter: dict) -> dict:
    html_files = sorted(output_dir.glob("*.html"))
    report = {
        "alt_text_added": [],
        "og_tags_added": [],
        "contrast_warnings": [],
        "sitemap_written": False,
    }

    for html_path in html_files:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
        changed = False

        for img in soup.find_all("img"):
            alt = img.get("alt")
            if not alt or not alt.strip():
                fallback = _fallback_alt_text(img.get("src", ""))
                img["alt"] = fallback
                report["alt_text_added"].append(f"{html_path.name}: {img.get('src')} -> {fallback}")
                changed = True

        if _inject_og_tags(soup, frontmatter, html_path.name):
            report["og_tags_added"].append(html_path.name)
            changed = True

        if changed:
            html_path.write_text(str(soup), encoding="utf-8")

    report["contrast_warnings"] = _check_contrast(frontmatter)

    _write_sitemap(output_dir, html_files)
    report["sitemap_written"] = True

    return report


def _fallback_alt_text(src: str) -> str:
    name = Path(src).stem
    name = re.sub(r"^[0-9a-f]{6,8}-", "", name)
    name = re.sub(r"-\d+x\d+$", "", name)
    words = [w for w in re.split(r"[-_]+", name) if w and not w.isdigit()]
    text = " ".join(words).strip()
    return text.title() if text else FALLBACK_ALT


def _inject_og_tags(soup: BeautifulSoup, frontmatter: dict, page_filename: str) -> bool:
    head = soup.find("head")
    if head is None:
        return False
    if head.find("meta", property="og:title"):
        return False

    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else frontmatter.get("site_name", "")
    description_tag = soup.find("meta", attrs={"name": "description"})
    description_text = description_tag.get("content", "") if description_tag else ""
    # frontmatter's logo path is relative to the project root (e.g.
    # "snapshot/image/xyz.png"); the generated output only has the same
    # basename under its own local images/ folder (see _copy_images).
    raw_logo_path = frontmatter.get("logo")
    logo_path = f"images/{Path(raw_logo_path).name}" if raw_logo_path else None

    og_pairs = [("og:type", "website"), ("og:title", title_text), ("og:description", description_text)]
    if logo_path:
        og_pairs.append(("og:image", logo_path))
    og_pairs.append(("og:url", page_filename))

    added_any = False
    for prop, content in og_pairs:
        if not content:
            continue
        tag = soup.new_tag("meta", property=prop, content=content)
        head.append(tag)
        added_any = True
    return added_any


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = _relative_luminance(_hex_to_rgb(hex1))
    l2 = _relative_luminance(_hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _check_contrast(frontmatter: dict) -> list[str]:
    colors = frontmatter.get("colors") or {}
    primary, secondary, accent = colors.get("primary"), colors.get("secondary"), colors.get("accent")
    pairs = [
        ("primary text on secondary background", primary, secondary),
        ("accent on secondary background", accent, secondary),
        ("primary on accent", primary, accent),
    ]
    warnings = []
    for label, c1, c2 in pairs:
        if not c1 or not c2:
            continue
        try:
            ratio = _contrast_ratio(c1, c2)
        except (ValueError, IndexError):
            continue
        if ratio < 4.5:
            warnings.append(f"{label} ({c1} vs {c2}): contrast ratio {ratio:.2f}:1 is below WCAG AA (4.5:1)")
    return warnings


def _write_sitemap(output_dir: Path, html_files: list[Path]) -> None:
    urls = "\n".join(
        f"  <url><loc>https://REPLACE-WITH-YOUR-DOMAIN.com/{p.name}</loc></url>" for p in html_files
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    (output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")
