"""Deterministic (no-AI) design-consistency guards for the all-pages build
(site_generator.generate_full_site). See
docs/seo-agent-and-buy-flow-plan.md, "Design consistency for the all-pages
build" (D1-D6) and breakage item 5a.

The full-site agent is told to reuse the home page's head/nav/footer and to
only append new component classes to the shared stylesheet, but prompting
alone doesn't guarantee it. These functions enforce the parts that can be
checked mechanically, after the agent batches have run:

- rewrite_internal_links: nav/body links that still point at the ORIGINAL
  live site's pages (the preview's nav is rendered from crawled hrefs) are
  rewritten to the local slug files.
- enforce_shared_head: every page loads the same stylesheets, fonts, CDN
  scripts and inline Tailwind config as index.html.
- sync_site_chrome: every page gets index.html's exact nav/header and
  footer markup.
- guard_appended_css: rules the agent appended to the shared stylesheet
  that would restyle existing pages (bare element selectors, or selectors
  already defined) are stripped.

Every function only rewrites a file when it actually changed something, so
an untouched file stays byte-identical.
"""

import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

HOME_FILENAME = "index.html"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")


def _other_pages(output_dir: Path) -> list[Path]:
    return [p for p in sorted(output_dir.glob("*.html")) if p.name != HOME_FILENAME]


def _outside_main(tag: Tag) -> bool:
    """True when `tag` isn't nested inside the page's own content (main /
    article) -- i.e. it's site chrome, not part of one page's body."""
    return not any(parent.name in ("main", "article") for parent in tag.parents)


# ---------------------------------------------------------------------------
# rewrite_internal_links (breakage item 5a)
# ---------------------------------------------------------------------------

_SKIP_HREF_PREFIXES = ("#", "mailto:", "tel:", "javascript:", "data:", "sms:")
_INDEX_SUFFIX_RE = re.compile(r"/(index|default)\.(html?|php|aspx?)$", re.IGNORECASE)


def _normalize_host(host: str) -> str:
    host = (host or "").lower().rsplit("@", 1)[-1].split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def _normalize_path(path: str) -> str:
    path = _INDEX_SUFFIX_RE.sub("/", path or "/")
    path = path.rstrip("/")
    return path.lower() or "/"


def build_url_to_filename_map(page_urls: list[str], filenames: list[str]) -> dict[tuple[str, str], str]:
    """(normalized host, normalized path) -> local filename, for every
    crawled page. Host/scheme/www/trailing-slash/index.html variants of the
    same page all normalize to the same key."""
    mapping: dict[tuple[str, str], str] = {}
    for url, filename in zip(page_urls, filenames):
        parts = urlsplit(url)
        mapping.setdefault((_normalize_host(parts.netloc), _normalize_path(parts.path)), filename)
    return mapping


def _resolve_local_target(href: str, base_url: str, url_map: dict, local_files: set[str]) -> str | None:
    href = href.strip()
    if not href or href.lower().startswith(_SKIP_HREF_PREFIXES):
        return None
    without_fragment, _, fragment = href.partition("#")
    if without_fragment in local_files:
        return None  # already a local page link
    try:
        absolute = urljoin(base_url, without_fragment)
        parts = urlsplit(absolute)
    except ValueError:
        return None
    if parts.query:
        return None  # a query string may mean a different resource; leave it
    filename = url_map.get((_normalize_host(parts.netloc), _normalize_path(parts.path)))
    if filename is None:
        return None
    return f"{filename}#{fragment}" if fragment else filename


def rewrite_internal_links(output_dir: Path, page_urls: list[str], filenames: list[str]) -> list[str]:
    """Rewrites every <a href> on every page that points at one of the
    crawled pages (absolute, root-relative or relative to the original
    site) to its local file. Only href values change. External and
    unmatched links are left alone. `page_urls[0]` (the crawled home page)
    is the base for relative hrefs."""
    if not page_urls:
        return []
    url_map = build_url_to_filename_map(page_urls, filenames)
    local_files = set(filenames)
    base_url = page_urls[0]
    changes: list[str] = []

    for html_path in sorted(output_dir.glob("*.html")):
        soup = _read_soup(html_path)
        changed = False
        for anchor in soup.find_all("a", href=True):
            target = _resolve_local_target(anchor["href"], base_url, url_map, local_files)
            if target is None or target == anchor["href"]:
                continue
            changes.append(f"{html_path.name}: {anchor['href']} -> {target}")
            anchor["href"] = target
            changed = True
        if changed:
            html_path.write_text(str(soup), encoding="utf-8")
    return changes


# ---------------------------------------------------------------------------
# enforce_shared_head (D4)
# ---------------------------------------------------------------------------

_SHARED_LINK_RELS = {"stylesheet", "preconnect", "preload", "dns-prefetch", "icon", "shortcut", "apple-touch-icon"}


def _head_asset_key(tag: Tag) -> tuple | None:
    """Identity of a shared <head> asset, or None if `tag` isn't one.
    Page-specific head content (title, meta description, canonical,
    JSON-LD) is deliberately not a shared asset."""
    if tag.name == "link":
        rels = {r.lower() for r in (tag.get("rel") or [])}
        if rels & _SHARED_LINK_RELS and tag.get("href"):
            return ("link", tuple(sorted(rels)), tag["href"].strip())
        return None
    if tag.name == "script":
        if tag.get("src"):
            return ("script-src", tag["src"].strip())
        script_type = (tag.get("type") or "").lower()
        if script_type == "application/ld+json":
            return None
        text = (tag.string or "").strip()
        if "tailwind" in text:
            return ("script-inline", text)
        return None
    if tag.name == "style":
        text = (tag.string or "").strip()
        if text and not tag.has_attr("data-seo-guard"):
            return ("style", text)
    return None


def shared_head_assets(home_soup: BeautifulSoup) -> list[Tag]:
    head = home_soup.find("head")
    if head is None:
        return []
    return [tag for tag in head.find_all(["link", "script", "style"], recursive=False) if _head_asset_key(tag)]


def enforce_shared_head(output_dir: Path) -> list[str]:
    """Adds any shared <head> asset index.html has (stylesheet/font/
    preconnect/icon links, CDN scripts, the inline Tailwind config, inline
    <style>) that another page is missing. Never removes anything. A
    missing asset is inserted right after the nearest earlier asset (in
    index.html's order) that the page does have, so ordering-sensitive
    pairs like the Tailwind CDN script + its inline config stay in order."""
    home_path = output_dir / HOME_FILENAME
    if not home_path.exists():
        return []
    home_assets = shared_head_assets(_read_soup(home_path))
    if not home_assets:
        return []
    changes: list[str] = []

    for page_path in _other_pages(output_dir):
        soup = _read_soup(page_path)
        head = soup.find("head")
        if head is None:
            continue
        present = {}
        for tag in head.find_all(["link", "script", "style"]):
            key = _head_asset_key(tag)
            if key is not None:
                present.setdefault(key, tag)

        changed = False
        previous_in_page: Tag | None = None
        for home_tag in home_assets:
            key = _head_asset_key(home_tag)
            if key in present:
                previous_in_page = present[key]
                continue
            clone = BeautifulSoup(str(home_tag), "lxml").find(home_tag.name)
            if previous_in_page is not None:
                previous_in_page.insert_after(clone)
            else:
                first_asset = next(
                    (t for t in head.find_all(["link", "script", "style"], recursive=False)), None
                )
                if first_asset is not None:
                    first_asset.insert_before(clone)
                else:
                    head.append(clone)
            present[key] = clone
            previous_in_page = clone
            changed = True
            changes.append(f"{page_path.name}: added {key[0]} {key[-1][:80]}")

        if changed:
            page_path.write_text(str(soup), encoding="utf-8")
    return changes


# ---------------------------------------------------------------------------
# sync_site_chrome (D5)
# ---------------------------------------------------------------------------


def _find_chrome(soup: BeautifulSoup, name: str) -> Tag | None:
    for tag in soup.find_all(name):
        if _outside_main(tag):
            return tag
    return None


def _header_is_pure_chrome(header: Tag) -> bool:
    """A header holding the page's own <h1>/hero must never be copied onto
    other pages -- only a plain nav bar."""
    return header.find("h1") is None


def home_chrome(home_soup: BeautifulSoup) -> dict[str, Tag]:
    """The home page's shared chrome: its top-level nav-bearing element
    (a hero-free <header>, otherwise a top-level <nav>) and its footer."""
    chrome: dict[str, Tag] = {}
    header = _find_chrome(home_soup, "header")
    if header is not None and _header_is_pure_chrome(header):
        chrome["header"] = header
    else:
        nav = _find_chrome(home_soup, "nav")
        if nav is not None and (header is None or header not in nav.parents):
            chrome["nav"] = nav
    footer = _find_chrome(home_soup, "footer")
    if footer is not None:
        chrome["footer"] = footer
    return chrome


def sync_site_chrome(output_dir: Path) -> list[str]:
    """Replaces each other page's top-level header/nav and footer with
    index.html's, when the page has a matching element to replace. Run
    after rewrite_internal_links, so the copied chrome already links to the
    local pages. A page without the element is left as is (nothing is
    added), and a page whose header holds its own <h1> keeps it."""
    home_path = output_dir / HOME_FILENAME
    if not home_path.exists():
        return []
    chrome = home_chrome(_read_soup(home_path))
    if not chrome:
        return []
    changes: list[str] = []

    for page_path in _other_pages(output_dir):
        soup = _read_soup(page_path)
        changed = False
        for name, home_tag in chrome.items():
            target = _find_chrome(soup, name)
            if target is None:
                continue
            if name == "header" and not _header_is_pure_chrome(target):
                continue
            if str(target) == str(home_tag):
                continue
            target.replace_with(BeautifulSoup(str(home_tag), "lxml").find(name))
            changed = True
            changes.append(f"{page_path.name}: {name} synced to {HOME_FILENAME}")
        if changed:
            page_path.write_text(str(soup), encoding="utf-8")
    return changes


def shared_shell_excerpt(home_html: str, max_chars: int = 12000) -> str:
    """D3: the home page's shared head assets + chrome markup, extracted by
    code for the full-site batch prompt, so the agent always has them even
    if it never calls read_file on index.html."""
    soup = BeautifulSoup(home_html, "lxml")
    parts = ["<!-- <head> assets every page must include -->"]
    parts += [str(tag) for tag in shared_head_assets(soup)]
    for name, tag in home_chrome(soup).items():
        parts.append(f"<!-- shared {name}: copy exactly -->")
        parts.append(str(tag))
    excerpt = "\n".join(parts)
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars] + "\n<!-- (truncated -- read_file index.html for the rest) -->"
    return excerpt


# ---------------------------------------------------------------------------
# guard_appended_css (D2)
# ---------------------------------------------------------------------------

_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# @-rules whose body is itself a list of style rules to filter recursively.
_NESTED_AT_RULES = ("@media", "@supports", "@layer", "@container")


def _split_css_blocks(css: str) -> list[tuple[str, str]] | None:
    """Top-level (prelude, body) pairs. Statement at-rules (`@import x;`)
    come back with body None-equivalent "" and a prelude ending in ";".
    Returns None when braces don't balance -- callers then leave the CSS
    alone rather than risk mangling it."""
    blocks: list[tuple[str, str]] = []
    i, n = 0, len(css)
    while i < n:
        while i < n and css[i].isspace():
            i += 1
        if i >= n:
            break
        brace = css.find("{", i)
        semicolon = css.find(";", i)
        if semicolon != -1 and (brace == -1 or semicolon < brace) and css[i] == "@":
            blocks.append((css[i : semicolon + 1].strip(), ""))
            i = semicolon + 1
            continue
        if brace == -1:
            if css[i:].strip():
                return None
            break
        prelude = css[i:brace].strip()
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        if depth:
            return None
        blocks.append((prelude, css[brace + 1 : j - 1]))
        i = j
    return blocks


def _normalize_selector(selector: str) -> str:
    return re.sub(r"\s+", " ", selector.strip()).lower()


def _is_bare_element_selector(selector: str) -> bool:
    """No class, id or attribute anywhere -- `body`, `h1`, `:root`, `*`,
    `section p`, `a:hover`. Such a rule restyles every page's existing
    markup, not just a new component."""
    return not any(ch in selector for ch in ".#[")


def _collect_selectors(css: str, into: set[str]) -> None:
    blocks = _split_css_blocks(_CSS_COMMENT_RE.sub("", css)) or []
    for prelude, body in blocks:
        if prelude.lower().startswith(_NESTED_AT_RULES):
            _collect_selectors(body, into)
        elif not prelude.startswith("@"):
            into.update(_normalize_selector(s) for s in prelude.split(","))


def _filter_rules(css: str, existing: set[str], stripped: list[str]) -> str | None:
    blocks = _split_css_blocks(css)
    if blocks is None:
        return None
    out: list[str] = []
    for prelude, body in blocks:
        lowered = prelude.lower()
        if prelude.endswith(";"):
            out.append(prelude)
            continue
        if lowered.startswith(_NESTED_AT_RULES):
            inner = _filter_rules(body, existing, stripped)
            if inner is None:
                return None
            if inner.strip():
                out.append(f"{prelude} {{\n{inner}\n}}")
            continue
        if prelude.startswith("@"):
            out.append(f"{prelude} {{{body}}}")  # @keyframes, @font-face: kept as is
            continue
        kept = []
        for selector in prelude.split(","):
            norm = _normalize_selector(selector)
            if _is_bare_element_selector(norm):
                stripped.append(f"{norm} (bare element selector)")
            elif norm in existing:
                stripped.append(f"{norm} (already defined)")
            else:
                kept.append(selector.strip())
        if kept:
            out.append(f"{', '.join(kept)} {{{body}}}")
    return "\n".join(out)


def guard_appended_css(css_path: Path, original_css: str) -> list[str]:
    """Strips rules the full-site agent appended to a shared stylesheet that
    would restyle existing pages: bare element selectors and selectors the
    original stylesheet already defines (a later rule wins the cascade, so
    "append-only" alone doesn't protect index.html's look). Only the
    appended part is inspected; the original stylesheet is never touched.
    Leaves the file alone if it can't be parsed safely."""
    if not css_path.exists():
        return []
    final_css = css_path.read_text(encoding="utf-8")
    base = original_css.rstrip("\n")
    if not final_css.startswith(base) or final_css == original_css:
        return []
    appended = final_css[len(base) :]
    existing: set[str] = set()
    _collect_selectors(original_css, existing)

    stripped: list[str] = []
    filtered = _filter_rules(_CSS_COMMENT_RE.sub("", appended), existing, stripped)
    if filtered is None or not stripped:
        return []
    css_path.write_text(base + "\n\n" + filtered.strip() + "\n", encoding="utf-8")
    return [f"{css_path.name}: stripped {s}" for s in stripped]
