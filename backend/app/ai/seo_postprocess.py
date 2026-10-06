"""Deterministic (no-AI) half of the post-purchase SEO pass -- see
app/ai/seo_agent.py and docs/seo-agent-and-buy-flow-plan.md ("How the SEO
pass works", "The 20-point checklist").

- audit_seo(): finds the problems the agent is asked to fix (and re-checks
  them afterwards): titles/descriptions, <h1> count, heading order, broken
  local links, weak alt text, noindex, http:// links.
- finalize_seo(): applies every mechanical item itself -- canonical,
  absolute OG/Twitter tags, html lang/charset/viewport, noindex removal,
  JSON-LD validation + anti-fabrication, image dimensions/lazy-loading,
  preconnect, safe script defer, image compression, sitemap.xml,
  robots.txt, llms.txt and SEO-NEXT-STEPS.md.

Everything here runs only on the generated/{tier}/seo/ copy, never on the
preview or full-site output it was copied from.
"""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from .blueprint_schema import BlueprintDocument
from .postprocess import page_url
from .site_consistency import _collect_selectors

TITLE_MAX = 60
DESCRIPTION_MIN = 120
DESCRIPTION_MAX = 160
IMAGE_MAX_WIDTH = 1920
JPEG_QUALITY = 82
WEBP_QUALITY = 80

IMG_HEIGHT_GUARD_RULE = ":where(img[width][height]){height:auto}"
IMG_HEIGHT_GUARD_MARKER = "/* seo: keep intrinsic image ratio */"

# CSS frameworks loaded from a CDN that style h1-h6 globally -- the audit
# can't read their CSS, so a page using one is never "safe to retag".
_HEADING_STYLING_FRAMEWORKS = ("bootstrap", "bulma", "foundation", "materialize", "uikit", "semantic", "pure-min")
_BARE_HEADING_RE = re.compile(r"^h[1-6](?::[\w-]+(?:\([^)]*\))?)*$")
_FILENAME_LIKE_ALT_RE = re.compile(r"^(image|img|photo|picture|dsc|screenshot)?[\s_-]*\d*$", re.IGNORECASE)
_SKIP_LINK_PREFIXES = ("#", "mailto:", "tel:", "javascript:", "data:", "sms:", "//", "http://", "https://")
_JSONLD_FABRICATION_KEYS = {
    "aggregateRating": "testimonials",
    "review": "testimonials",
    "offers": "pricing",
    "priceRange": "pricing",
    "award": "credentials",
}
_JSONLD_CONTACT_KEYS = ("telephone", "email", "address")


def _soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")


def html_pages(output_dir: Path) -> list[Path]:
    """index.html first, then every other page alphabetically."""
    pages = sorted(output_dir.glob("*.html"))
    return sorted(pages, key=lambda p: (p.name != "index.html", p.name))


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def _local_css_text(output_dir: Path, soup: BeautifulSoup) -> str:
    chunks = []
    for link in soup.find_all("link", href=True):
        rels = {r.lower() for r in (link.get("rel") or [])}
        href = link["href"].split("?")[0]
        if "stylesheet" in rels and not href.lower().startswith(_SKIP_LINK_PREFIXES):
            path = output_dir / href
            if path.is_file():
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    chunks += [style.get_text() for style in soup.find_all("style")]
    return "\n".join(chunks)


def heading_retag_safe(output_dir: Path, soup: BeautifulSoup) -> bool:
    """True only when changing an <h2> to an <h1> (or similar) can't change
    how the page looks: no local stylesheet/inline <style> has a rule for a
    bare heading element, and no CDN framework that styles headings
    globally (Bootstrap, Bulma, ...) is loaded."""
    for link in soup.find_all("link", href=True):
        if any(name in link["href"].lower() for name in _HEADING_STYLING_FRAMEWORKS):
            return False
    selectors: set[str] = set()
    _collect_selectors(_local_css_text(output_dir, soup), selectors)
    for selector in selectors:
        for compound in re.split(r"[\s>+~]+", selector):
            if _BARE_HEADING_RE.match(compound):
                return False
    return True


def _heading_sequence(soup: BeautifulSoup) -> list[str]:
    return [tag.name for tag in soup.find_all(re.compile(r"^h[1-6]$"))]


def _heading_skips(sequence: list[str]) -> list[str]:
    skips, previous = [], 0
    for name in sequence:
        level = int(name[1])
        if previous and level > previous + 1:
            skips.append(f"h{previous} -> {name}")
        previous = level
    return skips


def _broken_local_links(output_dir: Path, page: Path, soup: BeautifulSoup) -> list[str]:
    ids = {tag["id"] for tag in soup.find_all(id=True)}
    broken = []
    for tag, attr in (("a", "href"), ("img", "src"), ("script", "src"), ("link", "href")):
        for el in soup.find_all(tag, **{attr: True}):
            value = el[attr].strip()
            if not value:
                continue
            if value.startswith("#"):
                if tag == "a" and len(value) > 1 and value[1:] not in ids:
                    broken.append(value)
                continue
            if value.lower().startswith(_SKIP_LINK_PREFIXES):
                continue
            target = value.split("#")[0].split("?")[0]
            if not target:
                continue
            try:
                resolved = (output_dir / target).resolve()
            except (OSError, ValueError):
                broken.append(value)
                continue
            if not resolved.is_relative_to(output_dir.resolve()) or not resolved.exists():
                broken.append(value)
    return sorted(set(broken))


def _weak_alt(alt: str | None) -> bool:
    if alt is None:
        return True
    text = alt.strip()
    return bool(text) and (len(text) < 4 or bool(_FILENAME_LIKE_ALT_RE.match(text)) or text == "Image")


def audit_page(output_dir: Path, page: Path) -> dict:
    soup = _soup(page)
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = (description_tag.get("content") or "").strip() if description_tag else ""
    sequence = _heading_sequence(soup)
    robots = " ".join(
        (m.get("content") or "").lower() for m in soup.find_all("meta", attrs={"name": re.compile("^(robots|googlebot)$", re.I)})
    )
    return {
        "title": title,
        "title_length": len(title),
        "description": description,
        "description_length": len(description),
        "h1_count": sequence.count("h1"),
        "heading_skips": _heading_skips(sequence),
        "heading_retag_safe": heading_retag_safe(output_dir, soup),
        "images_missing_or_weak_alt": [
            img.get("src", "") for img in soup.find_all("img") if img.get("alt") is None or _weak_alt(img.get("alt"))
        ],
        "noindex": "noindex" in robots or "nofollow" in robots,
        "http_links": sorted(
            {el.get(attr) for tag, attr in (("a", "href"), ("img", "src"), ("script", "src"), ("link", "href"))
             for el in soup.find_all(tag, **{attr: True}) if el.get(attr, "").startswith("http://")}
        ),
        "broken_links": _broken_local_links(output_dir, page, soup),
        "has_jsonld": bool(soup.find("script", attrs={"type": "application/ld+json"})),
    }


def page_issues(audit: dict) -> list[str]:
    """Human-readable problems in one page's audit -- what the agent is told
    to fix, and what's left over in the final report."""
    issues = []
    if not audit["title"]:
        issues.append("missing <title>")
    elif audit["title_length"] > TITLE_MAX:
        issues.append(f"<title> is {audit['title_length']} chars (aim for <= {TITLE_MAX})")
    if not audit["description"]:
        issues.append("missing meta description")
    elif not DESCRIPTION_MIN <= audit["description_length"] <= DESCRIPTION_MAX:
        issues.append(
            f"meta description is {audit['description_length']} chars (aim for {DESCRIPTION_MIN}-{DESCRIPTION_MAX})"
        )
    if audit["h1_count"] != 1:
        issues.append(f"{audit['h1_count']} <h1> elements (should be exactly 1)")
    if audit["heading_skips"]:
        issues.append(f"heading levels skipped: {', '.join(audit['heading_skips'])}")
    if audit["images_missing_or_weak_alt"]:
        issues.append(f"{len(audit['images_missing_or_weak_alt'])} image(s) with missing or non-descriptive alt text")
    if audit["broken_links"]:
        issues.append(f"broken local links: {', '.join(audit['broken_links'][:10])}")
    if audit["noindex"]:
        issues.append("noindex/nofollow robots meta")
    if not audit["has_jsonld"]:
        issues.append("no JSON-LD structured data")
    return issues


def audit_seo(output_dir: Path) -> dict:
    pages = {page.name: audit_page(output_dir, page) for page in html_pages(output_dir)}
    titles = [a["title"] for a in pages.values() if a["title"]]
    descriptions = [a["description"] for a in pages.values() if a["description"]]
    duplicates = {
        "duplicate_titles": sorted({t for t in titles if titles.count(t) > 1}),
        "duplicate_descriptions": sorted({d for d in descriptions if descriptions.count(d) > 1}),
    }
    return {
        "pages": pages,
        "issues": {name: page_issues(audit) for name, audit in pages.items()},
        **duplicates,
    }


# ---------------------------------------------------------------------------
# JSON-LD validation + anti-fabrication (checklist #10)
# ---------------------------------------------------------------------------


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", str(value))


def blueprint_facts(blueprint: BlueprintDocument) -> dict:
    """What the original site actually stated -- the only facts structured
    data may claim."""
    phones, emails, addresses = set(), set(), []
    has = {"testimonials": False, "pricing": False, "credentials": False}
    for page in blueprint.pages:
        sections = page.sections
        if sections.contact.phone:
            phones.add(_digits(sections.contact.phone))
        if sections.contact.email:
            emails.add(sections.contact.email.strip().lower())
        if sections.contact.address:
            addresses.append(_norm_text(sections.contact.address))
        has["testimonials"] |= bool(sections.testimonials)
        has["pricing"] |= bool(sections.pricing)
        has["credentials"] |= bool(sections.credentials_awards)
    return {"phones": {p for p in phones if p}, "emails": emails, "address_text": " ".join(addresses), **has}


def _contact_value_known(key: str, value, facts: dict) -> bool:
    if key == "telephone":
        digits = _digits(value)
        return bool(digits) and any(digits.endswith(p[-7:]) or p.endswith(digits[-7:]) for p in facts["phones"])
    if key == "email":
        return str(value).strip().lower().removeprefix("mailto:") in facts["emails"]
    if key == "address":
        if not facts["address_text"]:
            return False
        strings = (
            [v for k, v in value.items() if not k.startswith("@") and isinstance(v, str)]
            if isinstance(value, dict)
            else [value] if isinstance(value, str) else []
        )
        return bool(strings) and all(_norm_text(s) in facts["address_text"] for s in strings)
    return True


def sanitize_jsonld(data, facts: dict, removed: list[str], path: str = "$"):
    """Recursively strips claims the source site never made: contact
    details not in the blueprint, and ratings/reviews/offers/prices/awards
    when the site had no testimonials/pricing/credentials."""
    if isinstance(data, list):
        return [sanitize_jsonld(item, facts, removed, f"{path}[{i}]") for i, item in enumerate(data)]
    if not isinstance(data, dict):
        return data
    cleaned = {}
    for key, value in data.items():
        source = _JSONLD_FABRICATION_KEYS.get(key)
        if source and not facts.get(source):
            removed.append(f"{path}.{key} (no {source} on the source site)")
            continue
        if key in _JSONLD_CONTACT_KEYS and not _contact_value_known(key, value, facts):
            removed.append(f"{path}.{key} (not in the source site's contact details)")
            continue
        cleaned[key] = sanitize_jsonld(value, facts, removed, f"{path}.{key}")
    return cleaned


def _fix_jsonld(soup: BeautifulSoup, facts: dict, report: dict, page_name: str) -> bool:
    changed = False
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            script.decompose()
            report["jsonld_dropped_invalid"].append(page_name)
            changed = True
            continue
        removed: list[str] = []
        cleaned = sanitize_jsonld(data, facts, removed)
        if removed:
            script.string = json.dumps(cleaned, ensure_ascii=False, indent=2)
            report["jsonld_fields_removed"] += [f"{page_name}: {r}" for r in removed]
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Head tags (checklist #3, #4, #15, #16, #18 + lang/charset/favicon)
# ---------------------------------------------------------------------------


def _ensure_head(soup: BeautifulSoup) -> Tag:
    head = soup.find("head")
    if head is None:
        head = soup.new_tag("head")
        html = soup.find("html")
        if html is None:
            html = soup.new_tag("html")
            soup.append(html)
        html.insert(0, head)
    return head


def _set_meta(soup: BeautifulSoup, head: Tag, attr: str, key: str, content: str, overwrite: bool) -> bool:
    if not content:
        return False
    tag = head.find("meta", attrs={attr: key})
    if tag is None:
        head.append(soup.new_tag("meta", attrs={attr: key, "content": content}))
        return True
    if overwrite and tag.get("content") != content:
        tag["content"] = content
        return True
    return False


def _absolute(site_origin: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return "https://" + path.split("://", 1)[1]
    return f"{site_origin}/{path.lstrip('./')}"


def _social_image(output_dir: Path, soup: BeautifulSoup, blueprint: BlueprintDocument) -> str | None:
    if blueprint.meta.logo:
        name = Path(blueprint.meta.logo).name
        if (output_dir / "images" / name).exists():
            return f"images/{name}"
    for page in blueprint.pages[:1]:
        background = page.sections.hero.background_image
        if background and (output_dir / "images" / Path(background).name).exists():
            return f"images/{Path(background).name}"
    first = soup.find("img", src=True)
    return first["src"] if first else None


def _fix_head(output_dir: Path, page: Path, soup: BeautifulSoup, blueprint: BlueprintDocument, site_origin: str, report: dict) -> bool:
    changed = False
    head = _ensure_head(soup)
    url = page_url(site_origin, page.name)

    html = soup.find("html")
    if html is not None and not html.get("lang"):
        html["lang"] = "en"
        changed = True
    if not head.find("meta", charset=True):
        head.insert(0, soup.new_tag("meta", charset="utf-8"))
        changed = True
    if not head.find("meta", attrs={"name": "viewport"}):
        head.append(soup.new_tag("meta", attrs={"name": "viewport", "content": "width=device-width, initial-scale=1"}))
        report["viewport_added"].append(page.name)
        changed = True

    for meta in head.find_all("meta", attrs={"name": re.compile("^(robots|googlebot)$", re.I)}):
        tokens = [t.strip() for t in (meta.get("content") or "").split(",") if t.strip()]
        kept = [t for t in tokens if t.lower() not in ("noindex", "nofollow", "none")]
        if kept != tokens:
            report["noindex_removed"].append(page.name)
            changed = True
            if kept:
                meta["content"] = ", ".join(kept)
            else:
                meta.decompose()

    canonical = head.find("link", rel=lambda r: r and "canonical" in r)
    if canonical is None:
        head.append(soup.new_tag("link", rel="canonical", href=url))
        changed = True
    elif canonical.get("href") != url:
        canonical["href"] = url
        changed = True

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else blueprint.meta.site_name
    description_tag = head.find("meta", attrs={"name": "description"})
    description = (description_tag.get("content") or "").strip() if description_tag else blueprint.meta.tagline
    image = _absolute(site_origin, _social_image(output_dir, soup, blueprint))

    changed |= _set_meta(soup, head, "property", "og:type", "website", overwrite=False)
    changed |= _set_meta(soup, head, "property", "og:site_name", blueprint.meta.site_name, overwrite=False)
    changed |= _set_meta(soup, head, "property", "og:title", title, overwrite=True)
    changed |= _set_meta(soup, head, "property", "og:description", description, overwrite=True)
    changed |= _set_meta(soup, head, "property", "og:url", url, overwrite=True)
    existing_og_image = head.find("meta", attrs={"property": "og:image"})
    if existing_og_image is not None and existing_og_image.get("content"):
        absolute = _absolute(site_origin, existing_og_image["content"])
        if absolute != existing_og_image["content"]:
            existing_og_image["content"] = absolute
            changed = True
        image = existing_og_image["content"]
    else:
        changed |= _set_meta(soup, head, "property", "og:image", image or "", overwrite=True)
    changed |= _set_meta(soup, head, "name", "twitter:card", "summary_large_image" if image else "summary", overwrite=False)
    changed |= _set_meta(soup, head, "name", "twitter:title", title, overwrite=True)
    changed |= _set_meta(soup, head, "name", "twitter:description", description, overwrite=True)
    if image:
        changed |= _set_meta(soup, head, "name", "twitter:image", image, overwrite=True)

    if blueprint.meta.favicon and not head.find("link", rel=lambda r: r and "icon" in r):
        name = Path(blueprint.meta.favicon).name
        if (output_dir / "images" / name).exists():
            head.append(soup.new_tag("link", rel="icon", href=f"images/{name}"))
            changed = True

    host = urlsplit(site_origin).netloc
    for tag, attr in (("a", "href"), ("img", "src"), ("link", "href"), ("script", "src")):
        for el in soup.find_all(tag, **{attr: True}):
            value = el[attr]
            if value.startswith("http://"):
                value_host = urlsplit(value).netloc.lower()
                if value_host in (host, f"www.{host}", host.removeprefix("www.")):
                    el[attr] = "https://" + value[len("http://"):]
                    report["https_rewritten"].append(f"{page.name}: {value}")
                    changed = True
                elif tag != "a":
                    report["mixed_content"].append(f"{page.name}: {value}")
    return changed


# ---------------------------------------------------------------------------
# Performance (checklist #13, #14)
# ---------------------------------------------------------------------------


def optimize_images(images_dir: Path) -> list[str]:
    """Downscales anything wider than IMAGE_MAX_WIDTH and re-encodes JPEG/
    PNG/WebP in place -- same filename, same format, so no reference
    breaks. Skips SVG, GIF/animated images and anything Pillow can't open;
    keeps the original whenever re-encoding wouldn't make it smaller."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover -- pillow is in requirements.txt
        return []
    results: list[str] = []
    if not images_dir.is_dir():
        return results
    for path in sorted(images_dir.iterdir()):
        suffix = path.suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png", ".webp") or not path.is_file():
            continue
        try:
            original_bytes = path.stat().st_size
            with Image.open(path) as img:
                if getattr(img, "is_animated", False):
                    continue
                img.load()
                fmt = img.format
                resized = False
                if img.width > IMAGE_MAX_WIDTH:
                    height = round(img.height * IMAGE_MAX_WIDTH / img.width)
                    img = img.resize((IMAGE_MAX_WIDTH, height), Image.LANCZOS)
                    resized = True
                tmp = path.with_name(path.name + ".seo-tmp")
                if fmt == "JPEG":
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.save(tmp, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
                elif fmt == "PNG":
                    img.save(tmp, "PNG", optimize=True)
                elif fmt == "WEBP":
                    img.save(tmp, "WEBP", quality=WEBP_QUALITY)
                else:
                    continue
            new_bytes = tmp.stat().st_size
            if resized or new_bytes < original_bytes:
                tmp.replace(path)
                results.append(f"{path.name}: {original_bytes} -> {new_bytes} bytes{' (resized)' if resized else ''}")
            else:
                tmp.unlink()
        except Exception:  # noqa: BLE001 -- a corrupt/odd image is skipped, never fatal
            leftover = path.with_name(path.name + ".seo-tmp")
            if leftover.exists():
                leftover.unlink()
            continue
    return results


def _image_size(output_dir: Path, src: str) -> tuple[int, int] | None:
    if not src or src.lower().startswith(_SKIP_LINK_PREFIXES) or src.lower().endswith(".svg"):
        return None
    try:
        from PIL import Image

        path = (output_dir / src.split("?")[0]).resolve()
        if not path.is_relative_to(output_dir.resolve()) or not path.is_file():
            return None
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:  # noqa: BLE001
        return None


def _fix_performance(output_dir: Path, page: Path, soup: BeautifulSoup, report: dict) -> bool:
    changed = False
    head = _ensure_head(soup)
    images = soup.find_all("img")
    # The likely LCP image is the first one in the page content, not the
    # logo in the header/nav -- fall back to the very first image otherwise.
    content_images = [
        img for img in images if not any(p.name in ("header", "nav", "footer") for p in img.parents)
    ]
    hero = content_images[0] if content_images else (images[0] if images else None)
    content_ids = {id(img) for img in content_images}  # identity, not Tag.__eq__ (structural)
    for img in images:
        if not (img.get("width") and img.get("height")):
            size = _image_size(output_dir, img.get("src", ""))
            if size:
                img["width"], img["height"] = str(size[0]), str(size[1])
                changed = True
        if img is hero:
            if img.get("loading") == "lazy":
                del img["loading"]
                changed = True
            if not img.get("fetchpriority"):
                img["fetchpriority"] = "high"
                changed = True
        else:
            # Header/nav logos are above the fold -- never lazy-load them.
            if id(img) in content_ids and not img.get("loading"):
                img["loading"] = "lazy"
                changed = True
            if not img.get("decoding"):
                img["decoding"] = "async"
                changed = True

    uses_google_fonts = any("fonts.googleapis.com" in (link.get("href") or "") for link in head.find_all("link"))
    if uses_google_fonts:
        existing = {link.get("href") for link in head.find_all("link", rel=lambda r: r and "preconnect" in r)}
        for href, crossorigin in (("https://fonts.googleapis.com", False), ("https://fonts.gstatic.com", True)):
            if href not in existing:
                tag = soup.new_tag("link", rel="preconnect", href=href)
                if crossorigin:
                    tag["crossorigin"] = ""
                first_link = head.find("link")
                if first_link is not None:
                    first_link.insert_before(tag)
                else:
                    head.append(tag)
                changed = True

    # `defer` only when no inline script could depend on a local script
    # having already run (JSON-LD isn't executable, so it doesn't count).
    inline_scripts = [
        s for s in soup.find_all("script")
        if not s.get("src") and (s.get("type") or "").lower() != "application/ld+json" and (s.string or "").strip()
    ]
    if not inline_scripts:
        for script in soup.find_all("script", src=True):
            src = script["src"]
            if src.lower().startswith(_SKIP_LINK_PREFIXES) or script.has_attr("defer") or script.has_attr("async"):
                continue
            if (script.get("type") or "").lower() == "module":
                continue
            script["defer"] = ""
            report["scripts_deferred"].append(f"{page.name}: {src}")
            changed = True
    return changed


def _ensure_img_height_guard(output_dir: Path, page: Path, soup: BeautifulSoup) -> bool:
    """Plan breakage item 5: width/height attributes can stretch an image
    when hand-written CSS sets width:100% without height:auto. A
    zero-specificity rule restores the ratio without overriding any
    class-based height. Lives in the page's local stylesheet when it has
    one, else in a marked inline <style>."""
    if not soup.find("img", attrs={"width": True, "height": True}):
        return False
    for link in soup.find_all("link", href=True):
        rels = {r.lower() for r in (link.get("rel") or [])}
        href = link["href"].split("?")[0]
        if "stylesheet" in rels and not href.lower().startswith(_SKIP_LINK_PREFIXES):
            css_path = output_dir / href
            if css_path.is_file():
                css = css_path.read_text(encoding="utf-8")
                if IMG_HEIGHT_GUARD_MARKER not in css:
                    css_path.write_text(css.rstrip("\n") + f"\n\n{IMG_HEIGHT_GUARD_MARKER}\n{IMG_HEIGHT_GUARD_RULE}\n", encoding="utf-8")
                return False  # the page's HTML itself didn't change
    head = _ensure_head(soup)
    if head.find("style", attrs={"data-seo-guard": True}):
        return False
    style = soup.new_tag("style", attrs={"data-seo-guard": ""})
    style.string = IMG_HEIGHT_GUARD_RULE
    head.append(style)
    return True


# ---------------------------------------------------------------------------
# Site-level files (checklist #1, #2, #19, #20)
# ---------------------------------------------------------------------------


def write_sitemap(output_dir: Path, site_origin: str) -> None:
    today = date.today().isoformat()
    urls = "\n".join(
        f"  <url><loc>{page_url(site_origin, p.name)}</loc><lastmod>{today}</lastmod></url>"
        for p in html_pages(output_dir)
    )
    (output_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n",
        encoding="utf-8",
    )


def write_robots_txt(output_dir: Path, site_origin: str) -> None:
    (output_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {site_origin}/sitemap.xml\n", encoding="utf-8"
    )


def write_llms_txt(output_dir: Path, site_origin: str, blueprint: BlueprintDocument, audit: dict) -> None:
    lines = [f"# {blueprint.meta.site_name}", ""]
    if blueprint.meta.tagline:
        lines += [f"> {blueprint.meta.tagline}", ""]
    lines.append("## Pages")
    for name, page_audit in audit["pages"].items():
        title = page_audit["title"] or name
        description = page_audit["description"]
        entry = f"- [{title}]({page_url(site_origin, name)})"
        lines.append(f"{entry}: {description}" if description else entry)
    (output_dir / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_next_steps(output_dir: Path, site_origin: str) -> None:
    (output_dir / "SEO-NEXT-STEPS.md").write_text(
        f"""# SEO: what's left for you to do

Your site's SEO basics (titles, descriptions, canonical links, structured
data, sitemap.xml, robots.txt, llms.txt, image sizes) are already in place.
These last steps happen outside the site files, so only you can do them:

1. **Publish on HTTPS.** Every link in these files uses `{site_origin}`.
   Turn on HTTPS at your host and redirect `http://` (and the `www`/non-`www`
   variant you don't use) to that address.
2. **Using a different domain?** Search-and-replace `{site_origin}` in every
   `.html` file, `sitemap.xml`, `robots.txt` and `llms.txt`.
3. **Google Search Console.** Add and verify your domain at
   https://search.google.com/search-console, then submit
   `{site_origin}/sitemap.xml` under *Sitemaps*.
4. **Bing Webmaster Tools** (optional). Same as above at
   https://www.bing.com/webmasters -- it can import from Search Console.
5. **Check old URLs.** If your old site used different page addresses,
   set up 301 redirects from the old addresses to the new pages so existing
   search rankings carry over.
""",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# finalize_seo
# ---------------------------------------------------------------------------


def finalize_seo(output_dir: Path, blueprint: BlueprintDocument, site_origin: str) -> dict:
    """Applies every mechanical SEO item to output_dir in place. Idempotent:
    running it twice adds nothing the second time."""
    report: dict = {
        "viewport_added": [],
        "noindex_removed": [],
        "https_rewritten": [],
        "mixed_content": [],
        "jsonld_dropped_invalid": [],
        "jsonld_fields_removed": [],
        "scripts_deferred": [],
        "images_optimized": optimize_images(output_dir / "images"),
    }
    facts = blueprint_facts(blueprint)
    for page in html_pages(output_dir):
        soup = _soup(page)
        changed = _fix_head(output_dir, page, soup, blueprint, site_origin, report)
        changed |= _fix_jsonld(soup, facts, report, page.name)
        changed |= _fix_performance(output_dir, page, soup, report)
        changed |= _ensure_img_height_guard(output_dir, page, soup)
        if changed:
            page.write_text(str(soup), encoding="utf-8")

    audit = audit_seo(output_dir)
    write_sitemap(output_dir, site_origin)
    write_robots_txt(output_dir, site_origin)
    write_llms_txt(output_dir, site_origin, blueprint, audit)
    write_next_steps(output_dir, site_origin)
    report["files_written"] = ["sitemap.xml", "robots.txt", "llms.txt", "SEO-NEXT-STEPS.md"]
    report["remaining_issues"] = {name: issues for name, issues in audit["issues"].items() if issues}
    report["duplicate_titles"] = audit["duplicate_titles"]
    report["duplicate_descriptions"] = audit["duplicate_descriptions"]
    return report
