"""Deterministic (no-AI) mapping of a crawled project's metadata.json + raw
HTML/assets into a schema-conformant BlueprintDocument -- scraped.json. This
is the direct replacement for the old blueprint_extractor.py's heuristic
half; see docs/blueprint-json-pipeline-plan.md for the full design.

The 14 named PageSections keys are a template of common sections, not an
exhaustive contract -- every one of them is always present (pydantic
defaults handle that), filled in where confidently found and left at its
empty default otherwise, for the review step to either fill (Mandatory
sections) or leave alone (Optional/no-fabrication sections). Real content
that doesn't match any of the 14 is never dropped: it's preserved under its
own site-derived heading in `additional_sections` instead (see
`_build_additional_sections`) -- the scraper's job is to lose nothing, not
to force everything into a fixed slot.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .blueprint_schema import (
    AboutSection,
    AdditionalSection,
    BlogItem,
    BlueprintDocument,
    ColorPalette,
    ContactSection,
    CredentialItem,
    CtaSection,
    FaqItem,
    Fonts,
    FooterSection,
    GalleryItem,
    HeroSection,
    MetaBlock,
    NavLink,
    PageBlueprint,
    PageImage,
    PageSections,
    PricingPlan,
    ServiceItem,
    SocialLink,
    StatItem,
    TeamMember,
    TestimonialItem,
)
from .color_extraction import extract_colors_from_css, extract_colors_from_image, gather_css_text
from .errors import BlueprintExtractionError

DEFAULT_COLORS = {"primary": "#333333", "secondary": "#f5f5f5", "accent": "#0066cc"}
DEFAULT_FONTS = {"heading": "Inter", "body": "Inter"}

EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
PHONE_RE = re.compile(r"(\+?\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")

SOCIAL_DOMAINS = (
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com", "pinterest.com",
)

# Class/id fallbacks for finding the real header/footer container on
# page-builder sites (Elementor, Divi, etc.) that don't emit semantic
# <header>/<footer>/<nav> tags at all, or that reuse <header> for something
# unrelated (e.g. a theme's page-title wrapper, commonly class="entry-header"
# -- which is exactly why a plain \bheader\b match isn't checked first: that
# pattern alone would match "entry-header" too, since a hyphen counts as a
# word boundary). STRONG_* targets well-known page-builder container
# conventions specifically and is checked before the literal tag; WEAK_*
# is a last-resort broad match, checked only after the literal tag, and
# still correctly excludes an unrelated widget class like
# "elementor-testimonial__footer" (no word boundary before "footer" there).
STRONG_HEADER_PATTERN = re.compile(r"location-header|site-header|main-header|masthead", re.IGNORECASE)
STRONG_FOOTER_PATTERN = re.compile(r"location-footer|site-footer|main-footer", re.IGNORECASE)
WEAK_HEADER_PATTERN = re.compile(r"\bheader\b", re.IGNORECASE)
WEAK_FOOTER_PATTERN = re.compile(r"\bfooter\b", re.IGNORECASE)
LINK_EXCLUDE_SCHEMES = ("tel:", "mailto:", "javascript:")

# Keyword haystacks (heading text + container id/class, lowercased) used to
# bucket a heading-anchored content block into a schema section. Checked in
# this order; first match wins. "cta_section" is re-routed to "contact"
# below if the block's own text contains an email/phone (a common overlap:
# "Ready to get started? Call us at ...").
SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "about": ("about", "who we are", "our story", "our mission", "why choose us"),
    "services_features": ("service", "feature", "what we do", "solution", "offering"),
    "faq": ("faq", "frequently asked", "question"),
    "cta_section": ("get started", "ready to", "book now", "sign up", "join us"),
    "testimonials": ("testimonial", "review", "what our client", "customer stor"),
    "team": ("team", "our staff", "meet the", "founder"),
    "pricing": ("pricing", "plans", "package"),
    "stats_social_proof": ("by the numbers", "years of experience", "clients served"),
    "credentials_awards": ("award", "certified", "accredited", "as seen in", "partner"),
    "blog_news": ("blog", "news", "latest", "article"),
    "gallery_portfolio": ("gallery", "portfolio", "our work", "project"),
    "contact": ("contact", "get in touch", "visit us", "location"),
}

LIST_TYPED_SECTIONS = (
    "services_features", "faq", "testimonials", "team", "pricing",
    "stats_social_proof", "credentials_awards", "blog_news",
)
MANDATORY_LIST_SECTIONS = ("services_features", "faq")


@dataclass
class ContentBlock:
    """One heading-anchored span of content: the heading itself (None for
    the page's pre-first-heading content) plus every descendant tag that
    fell between it and the next heading, in document order."""

    heading_text: str | None
    heading_level: int | None
    elements: list = field(default_factory=list)
    haystack: str = ""


def extract_scraped_json(project_root: Path) -> BlueprintDocument:
    """Reads project_root/metadata.json + the already-crawled page HTML and
    already-downloaded assets, and returns a fully schema-shaped
    BlueprintDocument. Raises BlueprintExtractionError for missing/invalid
    crawl data (unchanged contract from the old extract_blueprint())."""
    metadata_path = project_root / "metadata.json"
    if not metadata_path.exists():
        raise BlueprintExtractionError(f"No crawl metadata found at {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    pages_meta = metadata.get("pages") or []
    assets_meta = metadata.get("assets") or []

    if not pages_meta:
        raise BlueprintExtractionError("Crawl metadata has no pages to extract from")

    assets_by_url = {a["original_url"]: a for a in assets_meta}

    homepage_url = pages_meta[0]["url"]
    homepage_html = (project_root / pages_meta[0]["storage_path"]).read_text(encoding="utf-8")
    homepage_soup = BeautifulSoup(homepage_html, "lxml")

    site_name_guess = _guess_site_name(homepage_soup)
    logo_path = _assign_logo(homepage_soup, homepage_url, assets_by_url)
    favicon_path = _assign_favicon(homepage_soup, homepage_url, assets_by_url)

    css_text = gather_css_text(homepage_html, homepage_url)
    colors = extract_colors_from_css(css_text)
    if colors is None and logo_path:
        colors = extract_colors_from_image(project_root / logo_path)
    if colors is None:
        colors = DEFAULT_COLORS

    navigation = _extract_navigation(homepage_soup)

    pages: list[PageBlueprint] = []
    for page in pages_meta:
        html = (project_root / page["storage_path"]).read_text(encoding="utf-8")
        pages.append(_extract_page(page["url"], html, assets_by_url))

    meta = MetaBlock(
        site_name=site_name_guess or "Untitled Business",
        logo=logo_path,
        colors=ColorPalette(**colors),
        fonts=Fonts(**DEFAULT_FONTS),
        favicon=favicon_path,
    )

    return BlueprintDocument(meta=meta, navigation=navigation, pages=pages)


# --- Site-level (meta/navigation) heuristics -------------------------------


def _guess_site_name(soup: BeautifulSoup) -> str | None:
    og_site_name = soup.find("meta", property="og:site_name")
    if og_site_name and og_site_name.get("content"):
        return og_site_name["content"].strip()

    if soup.title and soup.title.get_text(strip=True):
        return re.split(r"[|\-–]", soup.title.get_text(strip=True))[0].strip()

    first_heading = soup.find(["h1", "h2", "h3"])
    if first_heading and first_heading.get_text(strip=True):
        return first_heading.get_text(strip=True)

    return None


def _resolve_image(img_tag, base_url: str, assets_by_url: dict) -> str | None:
    """Resolves an <img> tag's src to the already-downloaded asset's
    storage_path -- returns None (never a fabricated path) if the resolved
    absolute URL isn't in the already-downloaded assets list."""
    src = img_tag.get("src")
    if not src:
        return None
    absolute = urljoin(base_url, src)
    asset = assets_by_url.get(absolute)
    return asset["storage_path"] if asset else None


def _assign_logo(soup: BeautifulSoup, base_url: str, assets_by_url: dict) -> str | None:
    for img in soup.find_all("img"):
        haystack = " ".join(
            filter(
                None,
                [img.get("alt", ""), " ".join(img.get("class", []) or []), img.get("id", ""), img.get("src", "")],
            )
        ).lower()
        if "logo" in haystack:
            resolved = _resolve_image(img, base_url, assets_by_url)
            if resolved:
                return resolved

    header_scope = soup.find("header") or soup.find("nav")
    if header_scope:
        first_img = header_scope.find("img")
        if first_img:
            resolved = _resolve_image(first_img, base_url, assets_by_url)
            if resolved:
                return resolved

    for asset in assets_by_url.values():
        if asset.get("asset_type") == "image":
            return asset["storage_path"]

    return None


def _favicon_sizes_area(sizes: str) -> int:
    match = re.match(r"(\d+)x(\d+)", sizes or "")
    if not match:
        return 0
    return int(match.group(1)) * int(match.group(2))


def _assign_favicon(soup: BeautifulSoup, base_url: str, assets_by_url: dict) -> str | None:
    candidates: list[tuple[str, str]] = []
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" not in rel:
            continue
        absolute = urljoin(base_url, link["href"])
        asset = assets_by_url.get(absolute)
        if asset:
            candidates.append((link.get("sizes", ""), asset["storage_path"]))

    if not candidates:
        return None
    candidates.sort(key=lambda c: _favicon_sizes_area(c[0]), reverse=True)
    return candidates[0][1]


def _find_semantic_scope(
    soup: BeautifulSoup,
    tag_name: str,
    strong_pattern: re.Pattern,
    weak_pattern: re.Pattern,
    extra_ids: tuple[str, ...] = (),
):
    """Finds the real header/footer container. Checked in order: a
    known page-builder container convention (strongest, specific signal --
    checked BEFORE the literal tag since themes commonly reuse
    <header>/<footer> for something unrelated, e.g. a small page-title
    wrapper, which would otherwise shadow the real, larger container);
    the literal tag; a broad class/id keyword match (weakest, last resort
    before giving up); then known hardcoded ids (e.g. WordPress's
    conventional "colophon" footer id)."""
    for finder in (
        lambda: soup.find(class_=strong_pattern),
        lambda: soup.find(id=strong_pattern),
        lambda: soup.find(tag_name),
        lambda: soup.find(class_=weak_pattern),
        lambda: soup.find(id=weak_pattern),
    ):
        scope = finder()
        if scope is not None:
            return scope
    for extra_id in extra_ids:
        scope = soup.find(id=extra_id)
        if scope is not None:
            return scope
    return None


def _is_real_nav_link(href: str) -> bool:
    href_lower = href.strip().lower()
    if not href_lower or href_lower.startswith(LINK_EXCLUDE_SCHEMES):
        return False
    return not any(domain in href_lower for domain in SOCIAL_DOMAINS)


def _extract_navigation(soup: BeautifulSoup) -> list[NavLink]:
    nav_scope = soup.find("nav") or _find_semantic_scope(soup, "header", STRONG_HEADER_PATTERN, WEAK_HEADER_PATTERN)
    links: list[NavLink] = []
    if nav_scope:
        for anchor in nav_scope.find_all("a", href=True):
            href = anchor["href"]
            label = anchor.get_text(strip=True)
            if label and _is_real_nav_link(href):
                links.append(NavLink(label=label, href=href))
    return links


def _extract_footer(soup: BeautifulSoup) -> FooterSection:
    footer_tag = _find_semantic_scope(soup, "footer", STRONG_FOOTER_PATTERN, WEAK_FOOTER_PATTERN, extra_ids=("colophon",))
    if footer_tag is None:
        return FooterSection()

    links: list[NavLink] = []
    social_links: list[SocialLink] = []
    for anchor in footer_tag.find_all("a", href=True):
        href = anchor["href"]
        label = anchor.get_text(strip=True)
        domain_match = next((d for d in SOCIAL_DOMAINS if d in href.lower()), None)
        if domain_match:
            social_links.append(SocialLink(platform=domain_match.split(".")[0], url=href))
        elif label and _is_real_nav_link(href):
            links.append(NavLink(label=label, href=href))

    footer_text = footer_tag.get_text(" ", strip=True)
    copyright_match = re.search(r"(©|copyright)[^.]{0,80}", footer_text, re.IGNORECASE)
    return FooterSection(
        links=links,
        social_links=social_links,
        copyright_text=copyright_match.group(0).strip() if copyright_match else "",
    )


def _scan_contact_fallback(soup: BeautifulSoup) -> ContactSection:
    """Real contact info commonly lives outside any heading-anchored body
    block entirely -- e.g. a "call us" widget in the header (often a
    bare `tel:` link, which `_is_real_nav_link` deliberately excludes from
    navigation since it isn't a real nav destination) or a footer icon-list
    with an email. `_build_contact` only ever sees body_blocks, so this is
    a separate, best-effort fallback scan of the header/footer text only
    -- callers should use this only when the heading-based contact_entry
    came up empty, never to override real body-block content."""
    header_scope = soup.find("nav") or _find_semantic_scope(soup, "header", STRONG_HEADER_PATTERN, WEAK_HEADER_PATTERN)
    footer_scope = _find_semantic_scope(soup, "footer", STRONG_FOOTER_PATTERN, WEAK_FOOTER_PATTERN, extra_ids=("colophon",))
    combined_text = " ".join(
        scope.get_text(" ", strip=True) for scope in (header_scope, footer_scope) if scope is not None
    )
    email_match = EMAIL_RE.search(combined_text)
    phone_match = PHONE_RE.search(combined_text)
    return ContactSection(
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0).strip() if phone_match else "",
    )


def _collect_all_images(soup: BeautifulSoup, base_url: str, assets_by_url: dict) -> list[PageImage]:
    """Every downloaded image on the page, regardless of section role --
    the completeness net so nothing the crawler already downloaded is lost
    from the JSON just because no section heuristic claimed it."""
    seen_paths: set[str] = set()
    images: list[PageImage] = []
    for img in soup.find_all("img"):
        resolved = _resolve_image(img, base_url, assets_by_url)
        if resolved and resolved not in seen_paths:
            seen_paths.add(resolved)
            images.append(PageImage(path=resolved, alt=img.get("alt", "") or ""))
    return images


# --- Page segmentation & section classification -----------------------------


def _segment_page(main_scope) -> list[ContentBlock]:
    """Splits main_scope's descendants (document order) into heading-
    anchored spans. groups[0] is always the pre-first-heading content
    (heading_text=None)."""
    heading_names = {"h1", "h2", "h3"}
    groups: list[list] = [[None, None, []]]

    for el in main_scope.descendants:
        name = getattr(el, "name", None)
        if name is None:
            continue
        if name in heading_names:
            groups.append([el, int(name[1]), []])
        else:
            groups[-1][2].append(el)

    blocks: list[ContentBlock] = []
    for heading_tag, level, elements in groups:
        heading_text = heading_tag.get_text(strip=True) if heading_tag is not None else None
        haystack_parts = [heading_text or ""]
        if heading_tag is not None and heading_tag.parent is not None:
            container = heading_tag.parent
            haystack_parts.append(container.get("id", "") or "")
            haystack_parts.append(" ".join(container.get("class", []) or []))
        blocks.append(ContentBlock(heading_text, level, elements, " ".join(haystack_parts).lower()))

    return blocks


MIN_LEAF_TEXT_WORDS = 5


def _is_leaf_text_container(el) -> bool:
    """A <div>/<span> with no child *elements* at all (only text) --
    page-builder sites (Elementor, Divi, etc.) very commonly wrap prose in
    styled divs/spans instead of <p>, and today's tag-narrow extraction
    would otherwise miss that text entirely, in any section. Requiring no
    child elements (rather than allowing some and risking a parent+child
    both qualifying) sidesteps double-counting the same text twice, since
    `_segment_page` walks descendants as one flat list, not a tree --
    doesn't catch prose broken up by inline formatting tags (<strong>,
    <em>, ...), which is a known, accepted gap rather than a fix attempted
    here."""
    return el.name in ("div", "span") and not el.find_all(True)


def _block_paragraphs(block: ContentBlock) -> list[str]:
    texts = [e.get_text(" ", strip=True) for e in block.elements if e.name == "p" and e.get_text(strip=True)]
    for el in block.elements:
        if _is_leaf_text_container(el):
            text = el.get_text(" ", strip=True)
            if text and len(text.split()) >= MIN_LEAF_TEXT_WORDS:
                texts.append(text)
    return texts


def _block_list_items(block: ContentBlock) -> list[str]:
    return [e.get_text(" ", strip=True) for e in block.elements if e.name == "li" and e.get_text(strip=True)]


def _block_images(block: ContentBlock) -> list:
    return [e for e in block.elements if e.name == "img"]


def _block_links(block: ContentBlock) -> list:
    return [e for e in block.elements if e.name == "a"]


# Only `javascript:` and a bare "#" are filtered out here -- unlike nav
# links, tel:/mailto:/real same-page anchors (e.g. "#contactus") are
# legitimate, common CTA targets ("Call Now", "Book Now") and must not be
# dropped the way _is_real_nav_link would.
BROKEN_HREF_PREFIXES = ("javascript:",)


def _is_usable_href(href: str) -> bool:
    href = (href or "").strip()
    if not href or href == "#":
        return False
    return not href.lower().startswith(BROKEN_HREF_PREFIXES)


def _find_button_link(links: list):
    """Picks the best CTA candidate from `links`, filtering out unusable
    hrefs first (a javascript:-only or bare "#" href would otherwise get
    copied verbatim into a static site with no matching JS behind it, i.e.
    a dead button) -- prefers one styled like a button/CTA, falling back to
    the first remaining usable link, or None if none are usable."""
    usable_links = [link for link in links if _is_usable_href(link.get("href", ""))]
    for link in usable_links:
        haystack = " ".join(filter(None, [" ".join(link.get("class", []) or []), link.get("id", "")])).lower()
        if any(kw in haystack for kw in ("btn", "button", "cta")):
            return link
    return usable_links[0] if usable_links else None


def _looks_like_hero(block: ContentBlock, no_h1_on_page: bool = False) -> bool:
    """`no_h1_on_page` handles a common page-builder pattern (Elementor
    sites frequently skip <h1> entirely, using the theme's invisible page
    title instead and starting the visible content straight at <h2>) --
    when a page has zero <h1> tags anywhere, the first heading in document
    order IS the de facto hero headline regardless of its level or
    wording, since there's no stronger signal available to identify it."""
    return (
        block.heading_level == 1
        or no_h1_on_page
        or any(kw in block.haystack for kw in ("hero", "banner", "jumbotron"))
    )


def _classify_heading(block: ContentBlock) -> str | None:
    for section_key, keywords in SECTION_KEYWORDS.items():
        if any(kw in block.haystack for kw in keywords):
            if section_key == "cta_section":
                paragraph_text = " ".join(_block_paragraphs(block))
                if EMAIL_RE.search(paragraph_text) or PHONE_RE.search(paragraph_text):
                    return "contact"
            return section_key
    return None


def _build_hero(hero_blocks: list[ContentBlock], base_url: str, assets_by_url: dict, title_fallback: str) -> HeroSection:
    headline = next((b.heading_text for b in hero_blocks if b.heading_text), "") or title_fallback
    paragraphs = [p for b in hero_blocks for p in _block_paragraphs(b)]
    links = [link for b in hero_blocks for link in _block_links(b)]
    cta_link = _find_button_link(links)
    images = [img for b in hero_blocks for img in _block_images(b)]
    image_path = _resolve_image(images[0], base_url, assets_by_url) if images else None

    return HeroSection(
        headline=headline,
        subheadline=paragraphs[0] if paragraphs else "",
        cta_text=cta_link.get_text(strip=True) if cta_link is not None else "",
        cta_href=cta_link.get("href", "") if cta_link is not None else "",
        background_image=image_path,
    )


def _build_about(entry, base_url: str, assets_by_url: dict) -> AboutSection:
    if entry is None:
        return AboutSection()
    block, children = entry
    paragraphs = _block_paragraphs(block)
    for child in children:
        paragraphs.extend(_block_paragraphs(child))
    images = _block_images(block) or [img for child in children for img in _block_images(child)]
    image_path = _resolve_image(images[0], base_url, assets_by_url) if images else None
    return AboutSection(heading=block.heading_text or "", body=" ".join(paragraphs), image=image_path)


def _build_cta(entry) -> CtaSection:
    if entry is None:
        return CtaSection()
    block, _children = entry
    links = _block_links(block)
    cta_link = _find_button_link(links)
    return CtaSection(
        heading=block.heading_text or "",
        body=" ".join(_block_paragraphs(block)),
        cta_text=cta_link.get_text(strip=True) if cta_link is not None else "",
        cta_href=cta_link.get("href", "") if cta_link is not None else "",
    )


def _build_contact(entry) -> ContactSection:
    if entry is None:
        return ContactSection()
    block, children = entry
    combined_text = " ".join(p for b in (block, *children) for p in _block_paragraphs(b))
    email_match = EMAIL_RE.search(combined_text)
    phone_match = PHONE_RE.search(combined_text)
    return ContactSection(
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0).strip() if phone_match else "",
    )


def _item_from_block(section_key: str, block: ContentBlock, base_url: str, assets_by_url: dict):
    title = block.heading_text or ""
    body = " ".join(_block_paragraphs(block))
    images = _block_images(block)
    image_path = _resolve_image(images[0], base_url, assets_by_url) if images else None

    if section_key == "services_features":
        return ServiceItem(title=title, description=body, icon_image=image_path)
    if section_key == "faq":
        return FaqItem(question=title, answer=body)
    if section_key == "testimonials":
        return TestimonialItem(quote=body or title)
    if section_key == "team":
        return TeamMember(name=title, bio=body, photo=image_path)
    if section_key == "pricing":
        return PricingPlan(plan=title, features=_block_list_items(block))
    if section_key == "stats_social_proof":
        return StatItem(number=title, label=body)
    if section_key == "credentials_awards":
        return CredentialItem(name=title, badge_image=image_path)
    if section_key == "blog_news":
        return BlogItem(title=title, excerpt=body)
    raise ValueError(f"Unsupported list section key: {section_key}")


def _item_from_text(section_key: str, text: str):
    if section_key == "services_features":
        return ServiceItem(title=text[:60], description=text)
    if section_key == "faq":
        if "?" in text:
            question, _, answer = text.partition("?")
            return FaqItem(question=question.strip() + "?", answer=answer.strip())
        return FaqItem(question=text)
    raise ValueError(f"Unsupported list-from-text section key: {section_key}")


_ITEM_IMAGE_FIELDS = {"icon_image", "photo", "badge_image", "image"}


def _dedupe_items(items: list) -> list:
    """Drops exact-duplicate items (by every non-image field, case/whitespace
    -insensitive), keeping the first occurrence. Page-builder sites (notably
    Elementor) commonly duplicate an entire content block in the raw DOM for
    responsive breakpoints (one copy hidden via CSS per viewport size) --
    both copies get scraped since this heuristic layer doesn't evaluate
    CSS, so this is a deterministic, no-AI cleanup of that specific,
    common real-world pattern rather than a content judgment call."""
    seen: set[tuple] = set()
    deduped = []
    for item in items:
        dumped = item.model_dump()
        key = tuple(
            (field_name, str(value).strip().lower())
            for field_name, value in sorted(dumped.items())
            if field_name not in _ITEM_IMAGE_FIELDS
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_list_items(entries: list[tuple], section_key: str, base_url: str, assets_by_url: dict) -> list:
    items = []
    for parent_block, children in entries:
        if children:
            for child in children:
                items.append(_item_from_block(section_key, child, base_url, assets_by_url))
            continue

        list_items = _block_list_items(parent_block)
        if list_items and section_key in ("services_features", "faq"):
            items.extend(_item_from_text(section_key, text) for text in list_items)
        elif section_key in MANDATORY_LIST_SECTIONS:
            # No confident sub-structure -- still don't leave a Mandatory
            # section empty, use the whole block as a single item.
            items.append(_item_from_block(section_key, parent_block, base_url, assets_by_url))
        # else: Optional section with no confident structure -> leave empty,
        # per the no-fabrication rule (better empty than guessed).
    return _dedupe_items(items)


def _build_gallery(entries: list[tuple], base_url: str, assets_by_url: dict) -> list[GalleryItem]:
    items: list[GalleryItem] = []
    seen_paths: set[str] = set()
    for parent_block, children in entries:
        for block in (parent_block, *children):
            for img in _block_images(block):
                resolved = _resolve_image(img, base_url, assets_by_url)
                if resolved and resolved not in seen_paths:
                    seen_paths.add(resolved)
                    items.append(GalleryItem(image=resolved, caption=img.get("alt", "") or ""))
    return items


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _build_additional_sections(entries: list[tuple[int, ContentBlock]], base_url: str, assets_by_url: dict) -> list[AdditionalSection]:
    """Real, heading-anchored content that didn't match any of the 14
    named section types -- preserved under its own site-derived heading
    instead of being dropped (the schema's 14 keys are a template of
    common sections, not an exhaustive contract)."""
    sections: list[AdditionalSection] = []
    for _index, block in entries:
        title = block.heading_text or ""
        if not title:
            continue
        body = " ".join(_block_paragraphs(block))
        items = _block_list_items(block)
        images = []
        for img in _block_images(block):
            resolved = _resolve_image(img, base_url, assets_by_url)
            if resolved:
                images.append(resolved)
        if not body and not items and not images:
            continue  # heading with no real content under it -- nothing to preserve
        sections.append(AdditionalSection(key=_slugify(title), title=title, body=body, items=items, images=images))
    return sections


def _extract_footer_content_sections(footer_scope, base_url: str, assets_by_url: dict) -> PageSections:
    """Runs the same heading-based classification used for <main> against
    the footer's own content -- a "mega-footer" with its own About/Contact
    mini-sections (a common pattern: a 3-4 column footer with an About
    blurb, contact details, and social links each under their own real
    heading) is structurally just another region with headings, not only
    links/copyright the way `_extract_footer` treats it. Returns an empty
    PageSections if there's no footer or it has no headings of its own."""
    if footer_scope is None:
        return PageSections()
    blocks = _segment_page(footer_scope)
    if len(blocks) <= 1:
        return PageSections()
    body_blocks = blocks[1:]  # skip the footer's own pre-heading content (usually just a logo, not a real section)
    return _build_page_sections(body_blocks, base_url, assets_by_url)


def _merge_fill_empty_sections(primary: PageSections, secondary: PageSections) -> None:
    """Mutates `primary` in place: fills each field from `secondary` only
    where `primary` doesn't already have real content -- never overrides
    <main>-derived content. Used to bring in a mega-footer's own
    About/Contact/etc. mini-sections without risking clobbering better
    main-content data. Explicit per-field (not a generic reflection-based
    merge) to match this module's existing style."""
    if not primary.about.heading and not primary.about.body:
        primary.about = secondary.about
    if not primary.cta_section.heading and not primary.cta_section.body:
        primary.cta_section = secondary.cta_section
    if not primary.contact.email and not primary.contact.phone and not primary.contact.address:
        primary.contact = secondary.contact
    if not primary.services_features:
        primary.services_features = secondary.services_features
    if not primary.faq:
        primary.faq = secondary.faq
    if not primary.testimonials:
        primary.testimonials = secondary.testimonials
    if not primary.gallery_portfolio:
        primary.gallery_portfolio = secondary.gallery_portfolio
    if not primary.team:
        primary.team = secondary.team
    if not primary.pricing:
        primary.pricing = secondary.pricing
    if not primary.stats_social_proof:
        primary.stats_social_proof = secondary.stats_social_proof
    if not primary.credentials_awards:
        primary.credentials_awards = secondary.credentials_awards
    if not primary.blog_news:
        primary.blog_news = secondary.blog_news
    primary.additional_sections = primary.additional_sections + secondary.additional_sections


def _build_page_sections(body_blocks: list[ContentBlock], base_url: str, assets_by_url: dict) -> PageSections:
    classified: list[tuple[int, str, ContentBlock]] = []
    unclassified_indices: list[int] = []
    for index, block in enumerate(body_blocks):
        if block.heading_text is None:
            continue
        key = _classify_heading(block)
        if key:
            classified.append((index, key, block))
        else:
            unclassified_indices.append(index)

    classified_indices = {c[0] for c in classified}
    consumed: set[int] = set()
    grouped: dict[str, list[tuple]] = {key: [] for key in LIST_TYPED_SECTIONS}
    about_entry = cta_entry = contact_entry = None

    for index, key, block in classified:
        if index in consumed:
            continue
        children: list[ContentBlock] = []
        for next_index in range(index + 1, len(body_blocks)):
            if next_index in classified_indices:
                break
            candidate = body_blocks[next_index]
            if block.heading_level is None or candidate.heading_level is None:
                break
            if candidate.heading_level <= block.heading_level:
                break
            children.append(candidate)
            consumed.add(next_index)

        if key == "about" and about_entry is None:
            about_entry = (block, children)
        elif key == "cta_section" and cta_entry is None:
            cta_entry = (block, children)
        elif key == "contact" and contact_entry is None:
            contact_entry = (block, children)
        elif key in grouped:
            grouped[key].append((block, children))

    gallery_entries = grouped.pop("gallery_portfolio", [])

    # Heading blocks that never matched a keyword AND were never absorbed
    # as a child item of a classified parent (e.g. a service sub-heading) --
    # these are genuinely uncategorizable real content, preserved via
    # additional_sections rather than dropped.
    additional_entries = [
        (index, body_blocks[index]) for index in unclassified_indices if index not in consumed
    ]

    return PageSections(
        about=_build_about(about_entry, base_url, assets_by_url),
        services_features=_build_list_items(grouped["services_features"], "services_features", base_url, assets_by_url),
        faq=_build_list_items(grouped["faq"], "faq", base_url, assets_by_url),
        cta_section=_build_cta(cta_entry),
        testimonials=_build_list_items(grouped["testimonials"], "testimonials", base_url, assets_by_url),
        gallery_portfolio=_build_gallery(gallery_entries, base_url, assets_by_url),
        team=_build_list_items(grouped["team"], "team", base_url, assets_by_url),
        pricing=_build_list_items(grouped["pricing"], "pricing", base_url, assets_by_url),
        stats_social_proof=_build_list_items(grouped["stats_social_proof"], "stats_social_proof", base_url, assets_by_url),
        credentials_awards=_build_list_items(grouped["credentials_awards"], "credentials_awards", base_url, assets_by_url),
        contact=_build_contact(contact_entry),
        blog_news=_build_list_items(grouped["blog_news"], "blog_news", base_url, assets_by_url),
        additional_sections=_build_additional_sections(additional_entries, base_url, assets_by_url),
    )


# --- Known page-builder widget signatures -----------------------------------
#
# Content rendered as a self-contained widget (no governing heading at all)
# never enters the heading-anchored block model above and would otherwise be
# silently lost -- e.g. an Elementor "testimonial-carousel" widget. This is
# a small, explicit registry (section key -> extractor function) so adding
# another builder's convention later (pricing tables, team grids, stats
# counters) is a small addition, not a rewrite. Only entries with real
# evidence are wired up; no speculative ones for patterns not yet observed.


def _extract_elementor_testimonials(soup: BeautifulSoup, base_url: str, assets_by_url: dict) -> list[TestimonialItem]:
    items: list[TestimonialItem] = []
    for widget in soup.find_all(class_="elementor-testimonial"):
        text_el = widget.find(class_="elementor-testimonial__text")
        if text_el is None:
            continue
        quote = text_el.get_text(" ", strip=True)
        if not quote:
            continue
        name_el = widget.find(class_="elementor-testimonial__name")
        title_el = widget.find(class_="elementor-testimonial__title")
        items.append(
            TestimonialItem(
                quote=quote,
                author=name_el.get_text(strip=True) if name_el else "",
                role=title_el.get_text(strip=True) if title_el else "",
            )
        )
    return _dedupe_items(items)


WIDGET_EXTRACTORS = {
    "testimonials": _extract_elementor_testimonials,
}


def _extract_widget_sections(soup: BeautifulSoup, base_url: str, assets_by_url: dict, sections: PageSections) -> None:
    """Mutates `sections` in place: for each registered widget type, fills
    that section ONLY if the heading-based pass left it empty -- avoids
    double-counting on a site where that content genuinely is
    heading-anchored and was already correctly classified."""
    for section_key, extractor in WIDGET_EXTRACTORS.items():
        if getattr(sections, section_key):
            continue
        items = extractor(soup, base_url, assets_by_url)
        if items:
            setattr(sections, section_key, items)


def _extract_page(page_url: str, html: str, assets_by_url: dict) -> PageBlueprint:
    soup = BeautifulSoup(html, "lxml")
    all_images = _collect_all_images(soup, page_url, assets_by_url)
    main_scope = soup.find("main") or soup.body or soup
    blocks = _segment_page(main_scope)

    if not blocks:
        return PageBlueprint(page_url=page_url, sections=PageSections(), all_images=all_images)

    no_h1_on_page = main_scope.find("h1") is None
    pre_heading_block = blocks[0]
    if len(blocks) > 1 and _looks_like_hero(blocks[1], no_h1_on_page):
        hero_blocks = [pre_heading_block, blocks[1]]
        body_blocks = blocks[2:]
    else:
        hero_blocks = [pre_heading_block]
        body_blocks = blocks[1:]

    title_fallback = soup.title.get_text(strip=True) if soup.title else ""
    hero = _build_hero(hero_blocks, page_url, assets_by_url, title_fallback)

    sections = _build_page_sections(body_blocks, page_url, assets_by_url)
    sections.hero = hero
    sections.footer = _extract_footer(soup)
    _extract_widget_sections(soup, page_url, assets_by_url, sections)

    footer_scope = _find_semantic_scope(soup, "footer", STRONG_FOOTER_PATTERN, WEAK_FOOTER_PATTERN, extra_ids=("colophon",))
    footer_content_sections = _extract_footer_content_sections(footer_scope, page_url, assets_by_url)
    _merge_fill_empty_sections(sections, footer_content_sections)

    if not sections.contact.email or not sections.contact.phone:
        fallback_contact = _scan_contact_fallback(soup)
        sections.contact.email = sections.contact.email or fallback_contact.email
        sections.contact.phone = sections.contact.phone or fallback_contact.phone

    return PageBlueprint(page_url=page_url, sections=sections, all_images=all_images)
