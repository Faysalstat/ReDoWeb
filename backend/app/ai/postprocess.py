"""Deterministic post-processing over the agent's generated HTML output.

The generation agent is instructed to handle SEO/accessibility itself, but
nothing verifies it did. This module is the safety net: fills in any
missing/empty alt text, injects Open Graph tags if absent, runs a
best-effort WCAG AA contrast check against the blueprint's color palette
(flagged only -- never auto-"fixed", since a fix could contradict the
design), fixes up scroll-reveal CSS/JS gaps (see
`_fix_reveal_visibility_gaps`, auto-fixed since it's a mechanical bug, not
a content decision), and writes sitemap.xml.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from bs4 import BeautifulSoup

FALLBACK_ALT = "Image"
PLACEHOLDER_ORIGIN = "https://REPLACE-WITH-YOUR-DOMAIN.com"

# Real failure mode seen 2026-09-16: the agent writes JS that adds a class
# to reveal a scroll-triggered element (classList.add('is-visible')) but
# never writes the CSS rule for that revealed state -- the element (and
# everything inside it) stays at opacity:0 forever, i.e. the whole page
# between header and footer renders blank. These regexes are a static,
# heuristic cross-check between the generated CSS and JS, not a real
# parser of either -- see _find_js_reveal_pairs for why that's an
# acceptable tradeoff here.
_HIDDEN_DECL_RE = re.compile(r"opacity\s*:\s*0(?:\.0*)?\s*;|visibility\s*:\s*hidden\s*;")
_SIMPLE_CLASS_RULE_RE = re.compile(r"(?<![.\w-])\.([A-Za-z0-9_-]+)\s*\{([^{}]*)\}")
_JS_ADD_CLASS_RE = re.compile(r"classList\.(?:add|toggle)\(\s*['\"]([A-Za-z0-9_-]+)['\"]")
_QUERY_SELECTOR_CLASS_RE = re.compile(r"querySelector(?:All)?\(\s*['\"]\.([A-Za-z0-9_-]+)")
_REVEAL_PAIR_PROXIMITY_CHARS = 3000


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


def site_origin_from_url(source_url: str | None) -> str | None:
    """The redesign replaces the site the user submitted, so its domain is
    the real production origin for sitemap/canonical/og:url. Always https
    (the generated site should be served over HTTPS regardless of what the
    old one used). None when there's no usable host."""
    if not source_url:
        return None
    try:
        netloc = urlsplit(source_url.strip()).netloc
    except ValueError:
        return None
    netloc = netloc.rsplit("@", 1)[-1].lower()
    if not netloc or "." not in netloc or any(c.isspace() for c in netloc):
        return None
    return f"https://{netloc}"


def page_url(site_origin: str | None, filename: str) -> str:
    """Absolute public URL for a generated page -- index.html is the site root."""
    origin = site_origin or PLACEHOLDER_ORIGIN
    return f"{origin}/" if filename == "index.html" else f"{origin}/{filename}"


def postprocess_output(output_dir: Path, frontmatter: dict, site_origin: str | None = None) -> dict:
    html_files = sorted(output_dir.glob("*.html"))
    report = {
        "alt_text_added": [],
        "og_tags_added": [],
        "contrast_warnings": [],
        "reveal_visibility_fixes": [],
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

        if _inject_og_tags(soup, frontmatter, html_path.name, site_origin):
            report["og_tags_added"].append(html_path.name)
            changed = True

        if changed:
            html_path.write_text(str(soup), encoding="utf-8")

    report["contrast_warnings"] = _check_contrast(frontmatter)
    report["reveal_visibility_fixes"] = _fix_reveal_visibility_gaps(output_dir)

    _write_sitemap(output_dir, html_files, site_origin)
    report["sitemap_written"] = True

    return report


def _fallback_alt_text(src: str) -> str:
    name = Path(src).stem
    name = re.sub(r"^[0-9a-f]{6,8}-", "", name)
    name = re.sub(r"-\d+x\d+$", "", name)
    words = [w for w in re.split(r"[-_]+", name) if w and not w.isdigit()]
    text = " ".join(words).strip()
    return text.title() if text else FALLBACK_ALT


def _inject_og_tags(
    soup: BeautifulSoup, frontmatter: dict, page_filename: str, site_origin: str | None = None
) -> bool:
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
    if logo_path and site_origin:
        logo_path = f"{site_origin}/{logo_path}"

    og_pairs = [("og:type", "website"), ("og:title", title_text), ("og:description", description_text)]
    if logo_path:
        og_pairs.append(("og:image", logo_path))
    og_pairs.append(("og:url", page_url(site_origin, page_filename) if site_origin else page_filename))

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


def _find_hidden_by_default_classes(css_text: str) -> set[str]:
    """Class names with a standalone rule (".name{...}", not a compound
    selector) whose own declarations set opacity:0 or visibility:hidden --
    i.e. elements that start invisible and rely on something else (JS,
    normally) to reveal them."""
    hidden = set()
    for name, decls in _SIMPLE_CLASS_RULE_RE.findall(css_text):
        if _HIDDEN_DECL_RE.search(decls):
            hidden.add(name)
    return hidden


def _find_js_reveal_pairs(js_text: str, hidden_classes: set[str]) -> set[tuple[str, str]]:
    """Pairs a class JS adds via classList.add/toggle with whichever
    "starts hidden" class was most recently selected via
    querySelector(All) before it in the same file -- a proximity heuristic
    for "this add call is meant to reveal that element", not a real JS
    parse. False negatives (a reveal pattern written differently than
    this) just mean this check is skipped for that case; false positives
    just mean an extra, harmless override rule gets added below."""
    query_positions = [(m.start(), m.group(1)) for m in _QUERY_SELECTOR_CLASS_RE.finditer(js_text)]
    pairs = set()
    for add_match in _JS_ADD_CLASS_RE.finditer(js_text):
        add_class = add_match.group(1)
        add_pos = add_match.start()
        best = None
        for q_pos, q_class in query_positions:
            if q_pos >= add_pos:
                break
            if add_pos - q_pos > _REVEAL_PAIR_PROXIMITY_CHARS:
                continue
            if q_class in hidden_classes:
                best = q_class
        if best and best != add_class:
            pairs.add((best, add_class))
    return pairs


def _has_compound_override(css_text: str, class_a: str, class_b: str) -> bool:
    """True if some rule's selector already combines both classes (in
    either order) -- e.g. ".reveal.is-visible" or ".is-visible.reveal" --
    regardless of what it sets, since a rule the model wrote on purpose to
    react to both classes is assumed to be handling this correctly."""
    for selector in re.findall(r"([^{}]+)\{", css_text):
        if f".{class_a}" in selector and f".{class_b}" in selector:
            return True
    return False


def _fix_reveal_visibility_gaps(output_dir: Path) -> list[str]:
    """Safety net for a real, seen failure mode: the generation agent
    writes JS that adds a class to reveal a scroll-triggered element but
    never writes the matching CSS rule for that revealed state, so the
    element (and everything inside it) stays invisible forever. Fixed by
    appending a `!important` override rule rather than re-running the
    agent, since this is a mechanical CSS gap, not a content decision."""
    css_paths = sorted(output_dir.glob("*.css"))
    js_paths = sorted(output_dir.glob("*.js"))
    if not css_paths or not js_paths:
        return []

    js_text = "\n".join(p.read_text(encoding="utf-8") for p in js_paths)
    fixes: list[str] = []

    for css_path in css_paths:
        css_text = css_path.read_text(encoding="utf-8")
        hidden_classes = _find_hidden_by_default_classes(css_text)
        if not hidden_classes:
            continue

        additions = []
        for hidden_class, reveal_class in sorted(_find_js_reveal_pairs(js_text, hidden_classes)):
            if _has_compound_override(css_text, hidden_class, reveal_class):
                continue
            additions.append(
                f".{hidden_class}.{reveal_class}"
                "{opacity:1 !important;visibility:visible !important;transform:none !important}"
            )
            fixes.append(
                f"{css_path.name}: .{hidden_class}.{reveal_class} was never styled "
                "-- JS reveals it but nothing made it visible"
            )

        if additions:
            note = "\n/* Auto-added by postprocess: JS reveals this class but no CSS rule showed it */\n"
            css_path.write_text(css_text + note + "\n".join(additions) + "\n", encoding="utf-8")

    return fixes


def _write_sitemap(output_dir: Path, html_files: list[Path], site_origin: str | None = None) -> None:
    """Uses the real domain the user submitted when known (site_origin);
    the placeholder is only a fallback for projects with no usable
    source_url."""
    urls = "\n".join(f"  <url><loc>{page_url(site_origin, p.name)}</loc></url>" for p in html_files)
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    (output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")
