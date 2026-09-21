"""AI review pass: takes a deterministically-extracted BlueprintDocument
(scraped.json) and returns a reviewed copy (blueprint.json) in the exact
same schema shape. See docs/blueprint-json-pipeline-plan.md.

Three call types, fired concurrently via a ThreadPoolExecutor (thread-level
HTTP concurrency, capped per-project at `_worker_count()`'s ceiling below --
note that with multiple `queue_worker.py` processes running (see
docs/concurrency-scaling-plan.md), several projects' blueprint reviews can
now run at once, so total outbound OpenRouter connections scale with worker
count too, not just this per-project cap):
- Call A (meta, x1): reviews site_name/tagline/fonts/tone only.
- Call B (content, x1 per page): reviews the 5 Mandatory text-bearing
  sections (hero/about/services_features/faq/cta_section) of that one page,
  plus `additional_sections` -- real, site-specific content the extractor
  found that didn't match any of the 14 named section types (the schema is
  a template, not an exhaustive contract; see
  docs/blueprint-json-pipeline-plan.md). Review may improve wording within
  an existing additional_sections entry (same as any Mandatory section) but
  can never introduce a brand-new entry that wasn't already scraped -- the
  merge only ever accepts response entries matching an existing `key`.
- Call C (gap-check, x1 per page): a completeness safety net. Deterministic
  extraction heuristics only generalize to DOM patterns already coded for
  (confirmed by real gaps found via independent manual testing -- content
  living in a header/footer, a hero heading missed because the page had no
  <h1> at all); no amount of heuristic patching guarantees nothing is ever
  missed on a future site with novel structure. Call C is shown the page's
  full raw visible text (not scoped to <main>) plus a digest of everything
  already captured, and asked to find real content not reflected anywhere.
  It is the deliberate mirror image of Call B's additional_sections rule:
  Call B may only touch a `key` that already existed and must never invent
  one; Call C may only ADD new keys, and only ones backed by a verbatim
  quote code-verified (see `_verify_quote_in_text`) to actually appear in
  the page's real text -- it can never write into an existing named section
  (testimonials, contact, etc.) even if its own category guess suggests
  one, and an unverifiable claim is silently dropped, never surfaced.

The merge back into the document is code-enforced, not prompt-trusted: the
merge functions only ever read the keys/shapes they explicitly ask for, and
always overwrite image sub-fields with the original scraped value
regardless of what the model echoes back. navigation, footer, and all 8
Optional (no-fabrication) sections are never sent to Call A/B and are
copied byte-for-byte from the scraped document (Call C sees them only as
plain text inside the "already captured" digest, for gap-judging purposes,
and cannot write into them either).
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bs4 import BeautifulSoup

from .blueprint_schema import (
    AboutSection,
    AdditionalSection,
    BlueprintDocument,
    CtaSection,
    FaqItem,
    HeroSection,
    NavLink,
    PageBlueprint,
    PageSections,
    ServiceItem,
)
from .errors import OpenRouterError
from .font_library import DEFAULT_BODY_FONT, DEFAULT_HEADING_FONT, font_list_text, normalize_font
from .openrouter_client import vision_json_chat

META_REVIEW_SYSTEM_PROMPT = (
    "You are a brand analyst reviewing a scraped website's brand fields. "
    "You may be shown the site's logo image, plus its heuristically-guessed "
    "site name and a short digest of its real hero/about copy. Correct the "
    "site name only if the logo clearly shows a different or "
    "better-formatted name; otherwise leave it unchanged. Write a short "
    "tagline (max ~8 words) using only facts already present in the "
    "digest -- do not invent claims. Pick heading/body font families that "
    "visually match the logo's style, ONLY from this exact list (never the "
    "literal wordmark font, never a name outside this list):\n"
    f"{font_list_text()}\n\n"
    "Infer an overall tone in one short phrase (e.g. 'warm and friendly', "
    "'corporate and minimal').\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown fences) in this "
    "exact shape:\n"
    '{"site_name": string, "tagline": string, '
    '"fonts": {"heading": string, "body": string}, "tone": string}'
)

CONTENT_REVIEW_SYSTEM_PROMPT = (
    "You are a content and marketing editor reviewing one page's scraped "
    "sections from a small business website. You'll be shown the page's "
    "current hero/about/services_features/faq/cta_section content, plus "
    "any additional_sections (real content the scraper found that didn't "
    "match one of those standard types -- the site's own section, under "
    "its own heading), as JSON, plus a short digest of the rest of the "
    "site for fact-grounding.\n\n"
    "For each of the five standard sections plus each additional_sections "
    "entry:\n"
    "- If content is misplaced (e.g. FAQ-shaped content sitting in "
    "about.body), move it to the correct section.\n"
    "- If content is present but weak, rewrite it with clearer language, "
    "better structure, and a stronger marketing angle -- using only facts "
    "already present in the page or the site digest.\n"
    "- If services_features (or any list section, including an "
    "additional_sections entry's items) has near-duplicate items, or one "
    "item just re-lists facts already covered by other items (e.g. a "
    "summary entry repeating several other entries word-for-word), "
    "consolidate them -- keep the clearest single version, do not keep both.\n"
    "- If a section is empty and there is real source material elsewhere in "
    "the page or site digest to ground it in, draft short replacement copy "
    "in a tone matching the site's existing content -- but ONLY using facts "
    "already present in the page or site digest. Do not invent services, "
    "claims, numbers, or names not already there.\n"
    "- If a section is empty and there is NO groundable source material for "
    "it anywhere in the page or site digest (e.g. nothing FAQ-shaped exists "
    "to draw questions from), leave it empty -- do not invent generic "
    "filler content just to fill the key.\n\n"
    "For additional_sections specifically: you may rewrite an existing "
    "entry's title/body/items for clarity, and you may drop an entry "
    "entirely if it's genuinely redundant with another section -- but you "
    "must NEVER add a new additional_sections entry that wasn't already "
    "given to you. Every entry you return must reuse one of the exact "
    "`key` values you were shown; any entry with a key you invented "
    "yourself will be discarded, not added.\n\n"
    "Absolute rule: never draft, imply, or fill in testimonials/customer "
    "quotes, statistics or numeric claims, pricing, credentials/awards/"
    "certifications, team member names, gallery/portfolio images, blog "
    "posts, or contact details (email/phone/address) anywhere in your "
    "response -- those are handled elsewhere and are not part of what you "
    "were shown. Only touch hero/about/services_features/faq/cta_section/"
    "additional_sections.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown fences) with "
    "exactly these six keys, matching the input shape:\n"
    '{"hero": {"headline": string, "subheadline": string, "cta_text": '
    'string, "cta_href": string}, "about": {"heading": string, "body": '
    'string}, "services_features": [{"title": string, "description": '
    'string}], "faq": [{"question": string, "answer": string}], '
    '"cta_section": {"heading": string, "body": string, "cta_text": '
    'string, "cta_href": string}, "additional_sections": [{"key": string, '
    '"title": string, "body": string, "items": [string]}]}\n'
    "Do not include image fields (background_image, image, icon_image, "
    "images) in your response -- they are not reviewed by you, omit them "
    "entirely."
)

GAP_CHECK_SYSTEM_PROMPT = (
    "You are a completeness auditor comparing a website page's full visible "
    "text against a summary of what a content-extraction pass already "
    "captured from that same page. Your ONLY job is to find real, "
    "substantive content that exists verbatim in the page's visible text "
    "but is NOT reflected -- even in reworded form -- in the 'already "
    "captured' summary. Typical misses: content living in a page header or "
    "footer (announcement bars, secondary contact info, hours of "
    "operation), a heading or tagline the extractor placed nowhere, "
    "disclaimers, secondary calls-to-action, or any other real block of "
    "text the summary doesn't cover.\n\n"
    "Absolute rule: for every item you report, `quote` MUST be copied "
    "EXACTLY, character-for-character, from the supplied visible text -- "
    "do not paraphrase, translate, fix typos, or reformat it. If you "
    "cannot find an exact, contiguous quote for something, do not report "
    "it. Do not report anything already reflected in the 'already "
    "captured' summary, even if worded differently there. Do not invent, "
    "guess, or hallucinate content that isn't literally present in the "
    "visible text. Report at most 5 items, prioritizing the most "
    "substantial ones.\n\n"
    "Each `quote` should be one focused, contiguous span -- roughly one "
    "sentence to one short paragraph, never the whole page and never a "
    "single word.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown fences) in "
    "this exact shape:\n"
    '{"gaps": [{"quote": string, "title": string, "category": string}]}\n'
    "`title` is a short (max ~6 word) human-readable label (e.g. "
    "'Business Hours', 'Header Announcement'). `category` is your "
    "best-guess content type in a few words (e.g. 'testimonial', 'hours', "
    "'disclaimer', 'secondary cta') -- purely descriptive; it does not "
    "target or unlock writing into any existing named section. If there "
    'are no real gaps, respond with {"gaps": []}.'
)

MAX_PAGE_TEXT_CHARS = 12000  # ~3k tokens; caps Call C's dominant cost driver
MIN_GAP_QUOTE_CHARS = 15  # rejects trivial/junk matches ("the", "home", ...)
MAX_GAP_QUOTE_CHARS = 600  # rejects a "quote" that's really most of the page
MAX_GAPS_PER_PAGE = 5

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _load_page_storage_paths(project_root: Path) -> dict[str, str]:
    """url -> storage_path for every crawled page, read straight from
    metadata.json (the same field blueprint_extraction.py reads). Never
    raises -- returns {} on any missing/malformed metadata, which makes
    every page's gap-check degrade to zero gaps, consistent with Call
    A/B's existing degrade-on-failure contract."""
    try:
        metadata = json.loads((project_root / "metadata.json").read_text(encoding="utf-8"))
        return {p["url"]: p["storage_path"] for p in metadata.get("pages") or []}
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return {}


def _extract_visible_text(html: str) -> str:
    """The whole document's visible text -- deliberately NOT scoped to
    <main> like extraction is, since the entire point of this call is to
    see header/footer/anywhere-else content extraction structurally can't
    reach. Truncates head+tail rather than tail-only: the concrete blind
    spots this feature exists for (header content, footer content) sit at
    the very start/end of document-order text; the middle is where
    hero/about/services/etc already live and are already covered, so
    trimming there loses the least."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = _normalize_whitespace(soup.get_text(" ", strip=True))
    if len(text) <= MAX_PAGE_TEXT_CHARS:
        return text
    half = MAX_PAGE_TEXT_CHARS // 2
    return text[:half] + " ...[truncated]... " + text[-half:]


def _build_covered_content_digest(sections: PageSections, navigation: list[NavLink]) -> str:
    """Plain-text summary of EVERYTHING already captured for this page --
    all 14 sections + additional_sections + nav + footer, not just the 5
    Mandatory sections Call B reviews, since Call C's job is judging the
    whole extraction pass, not a subset of it."""
    lines: list[str] = []
    if navigation:
        lines.append("Nav links: " + ", ".join(link.label for link in navigation))
    if sections.hero.headline:
        lines.append(f"Hero headline: {sections.hero.headline}")
    if sections.hero.subheadline:
        lines.append(f"Hero subheadline: {sections.hero.subheadline}")
    if sections.about.body:
        lines.append(f"About: {sections.about.body}")
    for item in sections.services_features:
        lines.append(f"Service: {item.title} -- {item.description}")
    for item in sections.faq:
        lines.append(f"FAQ: {item.question} -- {item.answer}")
    if sections.cta_section.body or sections.cta_section.heading:
        lines.append(f"CTA: {sections.cta_section.heading} {sections.cta_section.body}")
    if sections.footer.copyright_text:
        lines.append(f"Footer copyright: {sections.footer.copyright_text}")
    if sections.footer.links:
        lines.append("Footer links: " + ", ".join(link.label for link in sections.footer.links))
    for item in sections.testimonials:
        lines.append(f"Testimonial: {item.quote} -- {item.author}")
    for item in sections.team:
        lines.append(f"Team: {item.name} -- {item.bio}")
    for item in sections.pricing:
        lines.append(f"Pricing: {item.plan} {item.price} {', '.join(item.features)}")
    for item in sections.stats_social_proof:
        lines.append(f"Stat: {item.number} {item.label}")
    for item in sections.credentials_awards:
        lines.append(f"Credential: {item.name}")
    if sections.contact.email or sections.contact.phone or sections.contact.address:
        lines.append(
            f"Contact: {sections.contact.email} {sections.contact.phone} "
            f"{sections.contact.address} {sections.contact.hours}"
        )
    for item in sections.blog_news:
        lines.append(f"Blog: {item.title} -- {item.excerpt}")
    for item in sections.additional_sections:
        lines.append(f"Additional ({item.key}): {item.title} -- {item.body} {' '.join(item.items)}")
    return "\n".join(lines) or "(nothing captured yet for this page)"


def _verify_quote_in_text(quote: str, normalized_page_text: str) -> bool:
    """The core anti-fabrication gate for Call C: a claimed gap is only
    ever accepted if it's an exact, whitespace-normalized substring of the
    page's real text. This is the same 'code-enforced, not prompt-trusted'
    pattern the no-fabrication guarantee relies on everywhere else in this
    pipeline (e.g. _resolve_image never assigning a path the crawler
    didn't actually download)."""
    normalized_quote = _normalize_whitespace(quote)
    if not (MIN_GAP_QUOTE_CHARS <= len(normalized_quote) <= MAX_GAP_QUOTE_CHARS):
        return False
    return normalized_quote in normalized_page_text


def _unique_gap_key(title: str, existing_keys: set[str]) -> str:
    base = "gap-" + (re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section")
    candidate, suffix = base, 2
    while candidate in existing_keys:
        candidate = f"{base}-{suffix}"
        suffix += 1
    existing_keys.add(candidate)
    return candidate


def _review_page_gaps(
    project_root: Path,
    storage_path: str | None,
    original: PageSections,
    navigation: list[NavLink],
    model: str | None = None,
) -> tuple[list[AdditionalSection], dict]:
    """Call C: finds real content the deterministic extraction missed
    anywhere on the page (not just <main>), verifies each claim against
    the actual page text, and returns only verified findings as brand-new
    additional_sections entries. Degrades to ([], {}) on any failure --
    missing metadata, missing/unreadable HTML, OpenRouter failure, or a
    malformed response -- exactly like Call A/B's degrade-on-failure
    contract; this is an additive safety net, never a hard dependency."""
    if not storage_path:
        return [], {}
    try:
        html = (project_root / storage_path).read_text(encoding="utf-8")
    except OSError:
        return [], {}

    page_text = _extract_visible_text(html)
    if not page_text:
        return [], {}

    digest = _build_covered_content_digest(original, navigation)
    user_text = (
        f"Full visible text of this page:\n{page_text}\n\n"
        f"Content already captured for this page (do not re-flag anything "
        f"reflected here, even if worded differently):\n{digest}"
    )

    try:
        result, usage = vision_json_chat(GAP_CHECK_SYSTEM_PROMPT, user_text, [], model=model)
    except OpenRouterError:
        return [], {}

    raw_gaps = result.get("gaps")
    if not isinstance(raw_gaps, list):
        return [], {}

    existing_keys = {section.key for section in original.additional_sections}
    verified: list[AdditionalSection] = []
    for gap in raw_gaps[:MAX_GAPS_PER_PAGE]:
        if not isinstance(gap, dict):
            continue
        quote = gap.get("quote")
        if not isinstance(quote, str) or not _verify_quote_in_text(quote, page_text):
            continue  # unverifiable claim -- discarded outright, never surfaced
        title = str(gap.get("title") or "Additional Content").strip()
        category = str(gap.get("category") or "").strip()
        verified.append(
            AdditionalSection(
                key=_unique_gap_key(title, existing_keys),
                title=f"{title} ({category})" if category else title,
                body=_normalize_whitespace(quote),
                items=[],
                images=[],
            )
        )
    return verified, usage


def _merge_gap_sections(existing: list[AdditionalSection], verified_gaps: list[AdditionalSection]) -> list[AdditionalSection]:
    """The deliberate mirror image of _merge_content_review: that function
    only ever accepts a `key` already present in the original document and
    never adds one; this function only ever adds keys that were already
    proven (in _review_page_gaps, via _unique_gap_key against the same
    keyspace and a code-verified quote) to be new and real. A plain
    concatenation is safe specifically because that uniqueness and
    verification happened upstream, not here."""
    return existing + verified_gaps


def _worker_count(num_pages: int, include_meta: bool) -> int:
    """1 meta + 2 calls (content, gap) per targeted page. Capped at 16 --
    not for correctness (concurrency here only ever affects latency, never
    correctness), but to bound simultaneous outbound OpenRouter connections
    now that a single review batch can span up to ~19 pages (the
    remaining-pages-after-home-page case triggered by a full-site purchase,
    see tasks_full_site.py) rather than the old 3-page-cap assumption this
    replaces."""
    return min((1 if include_meta else 0) + 2 * num_pages, 16) or 1


def review_blueprint(
    project_root: Path,
    scraped: BlueprintDocument,
    model: str | None = None,
    page_indices: list[int] | None = None,
    include_meta: bool = True,
) -> tuple[BlueprintDocument, dict]:
    """`model` overrides the OpenRouter model id used for all three call
    types below (real callers resolve it once from the DB-backed
    model_config_service.get_vision_model() in blueprint_pipeline.py and
    pass it down here; omitted, each call falls back to config.py's static
    vision_model default).

    `page_indices` restricts Call B/C to only these positions in
    `scraped.pages` -- the returned document's `.pages` is filtered down to
    just those indices, in the given order, rather than the full original
    list. None (default) reviews every page, matching the original
    behavior -- used by the DB-free debug routes and a from-scratch full
    re-review. The real pipeline's initial run passes `page_indices=[0]`
    (home page only, see tasks_blueprint.py); a full-site purchase later
    passes just the remaining indices (see tasks_full_site.py).

    `include_meta=False` skips Call A entirely and leaves `blueprint.meta`
    as `scraped.meta` untouched -- used when re-reviewing the remaining
    pages after a purchase, since meta was already resolved (and possibly
    AI-corrected) by the original home-page run and doesn't need re-spending.
    """
    blueprint = scraped.model_copy(deep=True)
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    target_indices = page_indices if page_indices is not None else list(range(len(scraped.pages)))

    logo_path = scraped.meta.logo
    image_paths = [project_root / logo_path] if logo_path else []
    meta_digest = _build_meta_digest(scraped)
    storage_paths_by_url = _load_page_storage_paths(project_root)

    with ThreadPoolExecutor(max_workers=_worker_count(len(target_indices), include_meta)) as executor:
        meta_future = (
            executor.submit(
                vision_json_chat,
                META_REVIEW_SYSTEM_PROMPT,
                f"Heuristic site name guess: {scraped.meta.site_name}\n\n{meta_digest}",
                image_paths,
                model=model,
            )
            if include_meta
            else None
        )
        content_futures = [
            executor.submit(_review_page, scraped.pages[i], scraped, i, model) for i in target_indices
        ]
        gap_futures = [
            executor.submit(
                _review_page_gaps,
                project_root,
                storage_paths_by_url.get(scraped.pages[i].page_url),
                scraped.pages[i].sections,
                scraped.navigation,
                model,
            )
            for i in target_indices
        ]

        if meta_future is None:
            meta_result, meta_usage = {}, {}
        else:
            try:
                meta_result, meta_usage = meta_future.result()
            except OpenRouterError:
                # Every meta field now has a working heuristic fallback, so a
                # meta-review failure degrades instead of failing the whole
                # pipeline (supersedes the old brand-review fail-hard rule --
                # see docs/blueprint-json-pipeline-plan.md).
                meta_result, meta_usage = {}, {}

        page_results = [future.result() for future in content_futures]
        gap_results = [future.result() for future in gap_futures]

    total_usage["prompt_tokens"] += meta_usage.get("prompt_tokens", 0)
    total_usage["completion_tokens"] += meta_usage.get("completion_tokens", 0)

    if include_meta:
        blueprint.meta.site_name = meta_result.get("site_name") or scraped.meta.site_name
        blueprint.meta.tagline = meta_result.get("tagline") or scraped.meta.tagline
        fonts = meta_result.get("fonts") or {}
        # Code-enforced, not just prompted -- the meta-review call is a
        # free-text vision guess, and it has genuinely hallucinated a
        # plausible-but-fake font name in practice ("Pawtastic" for a
        # dog-themed logo), which would otherwise silently fail to load and
        # fall back to generic sans-serif in generated CSS. See font_library.py.
        heading_fallback = normalize_font(scraped.meta.fonts.heading, DEFAULT_HEADING_FONT)
        body_fallback = normalize_font(scraped.meta.fonts.body, DEFAULT_BODY_FONT)
        blueprint.meta.fonts.heading = normalize_font(fonts.get("heading"), heading_fallback)
        blueprint.meta.fonts.body = normalize_font(fonts.get("body"), body_fallback)
        blueprint.meta.tone = meta_result.get("tone") or scraped.meta.tone

    # Filter down to just the targeted pages, in target_indices' order.
    # From here on, blueprint.pages[position] and
    # page_results[position]/gap_results[position] are aligned by position
    # in target_indices, NOT by the pages' original index in scraped.pages.
    blueprint.pages = [blueprint.pages[i] for i in target_indices]

    # Call B's result becomes the base for each page first (its own,
    # subset-filtered additional_sections); Call C's verified new entries
    # are appended on top, never the other way around -- see
    # _merge_gap_sections' docstring for why this ordering is safe.
    for position, (reviewed_sections, usage) in enumerate(page_results):
        blueprint.pages[position].sections = reviewed_sections
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

    for position, (verified_gaps, usage) in enumerate(gap_results):
        blueprint.pages[position].sections.additional_sections = _merge_gap_sections(
            blueprint.pages[position].sections.additional_sections, verified_gaps
        )
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

    return blueprint, total_usage


def _build_meta_digest(scraped: BlueprintDocument) -> str:
    home = scraped.pages[0].sections if scraped.pages else PageSections()
    lines = []
    if home.hero.headline:
        lines.append(f"Hero headline: {home.hero.headline}")
    if home.hero.subheadline:
        lines.append(f"Hero subheadline: {home.hero.subheadline}")
    if home.about.body:
        lines.append(f"About: {home.about.body[:300]}")
    return "\n".join(lines) or "(no scraped hero/about copy available)"


def _build_site_digest(scraped: BlueprintDocument, exclude_index: int) -> str:
    blocks = []
    for index, page in enumerate(scraped.pages):
        if index == exclude_index:
            continue
        sections = page.sections
        lines = [f"Page: {page.page_url}"]
        if sections.hero.headline:
            lines.append(f"Hero: {sections.hero.headline}")
        if sections.about.body:
            lines.append(f"About: {sections.about.body[:200]}")
        has_contact = bool(sections.contact.email or sections.contact.phone)
        lines.append(f"Contact info found: {'yes' if has_contact else 'no'}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or "(single-page site, no other pages)"


def _review_page(
    page: PageBlueprint, scraped: BlueprintDocument, index: int, model: str | None = None
) -> tuple[PageSections, dict]:
    original = page.sections
    request_payload = {
        "hero": original.hero.model_dump(exclude={"background_image"}),
        "about": original.about.model_dump(exclude={"image"}),
        "services_features": [item.model_dump(exclude={"icon_image"}) for item in original.services_features],
        "faq": [item.model_dump() for item in original.faq],
        "cta_section": original.cta_section.model_dump(),
        "additional_sections": [
            section.model_dump(exclude={"images"}) for section in original.additional_sections
        ],
    }
    digest = _build_site_digest(scraped, exclude_index=index)
    user_text = (
        f"This page's current sections:\n{json.dumps(request_payload, indent=2)}\n\n"
        f"Rest of the site (for fact-grounding only):\n{digest}"
    )

    try:
        result, usage = vision_json_chat(CONTENT_REVIEW_SYSTEM_PROMPT, user_text, [], model=model)
    except OpenRouterError:
        # Additive enhancement -- degrade to the unreviewed sections rather
        # than failing the whole pipeline over one page's review call.
        return original, {}

    return _merge_content_review(original, result), usage


def _merge_content_review(original: PageSections, result: dict) -> PageSections:
    """Code-enforced merge: only ever reads the 5 allowed keys off `result`;
    image sub-fields always come from `original`, never from the model's
    response. Everything else (navigation is document-level, footer, and
    all 8 Optional sections) is an untouched deep copy of `original`."""
    merged = original.model_copy(deep=True)

    hero = result.get("hero") or {}
    merged.hero = HeroSection(
        headline=hero.get("headline") or original.hero.headline,
        subheadline=hero.get("subheadline") or original.hero.subheadline,
        cta_text=hero.get("cta_text") or original.hero.cta_text,
        cta_href=hero.get("cta_href") or original.hero.cta_href,
        background_image=original.hero.background_image,
    )

    about = result.get("about") or {}
    merged.about = AboutSection(
        heading=about.get("heading") or original.about.heading,
        body=about.get("body") or original.about.body,
        image=original.about.image,
    )

    services = result.get("services_features")
    if isinstance(services, list):
        # `isinstance` alone, not `and services`: the prompt explicitly
        # allows the model to consolidate services_features down to
        # nothing if every item was redundant, and an empty list is that
        # deliberate signal -- treating it the same as "key missing" would
        # make that outcome unreachable and silently keep stale originals.
        # Matched by title, not position: the prompt explicitly asks the
        # model to consolidate/drop near-duplicate items, so the returned
        # list's length and order can't be assumed to line up with
        # `original`'s -- positional pairing would silently attach the
        # wrong icon to a surviving item. Falls back to positional only
        # when the count is unchanged (title got reworded but nothing was
        # added/removed/reordered); otherwise no icon rather than a
        # guessed-wrong one.
        original_by_title = {item.title.strip().lower(): item.icon_image for item in original.services_features}
        original_icons_positional = [item.icon_image for item in original.services_features]
        same_count = len(services) == len(original.services_features)
        merged_services = []
        for i, item in enumerate(services):
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            icon = original_by_title.get(title.strip().lower())
            if icon is None and same_count:
                icon = original_icons_positional[i]
            merged_services.append(ServiceItem(title=title, description=item.get("description", ""), icon_image=icon))
        merged.services_features = merged_services

    faq = result.get("faq")
    if isinstance(faq, list):  # empty list is a deliberate "drop them all" signal, not "no response"
        merged.faq = [
            FaqItem(question=item.get("question", ""), answer=item.get("answer", ""))
            for item in faq
            if isinstance(item, dict)
        ]

    cta = result.get("cta_section") or {}
    merged.cta_section = CtaSection(
        heading=cta.get("heading") or original.cta_section.heading,
        body=cta.get("body") or original.cta_section.body,
        cta_text=cta.get("cta_text") or original.cta_section.cta_text,
        cta_href=cta.get("cta_href") or original.cta_section.cta_href,
    )

    additional = result.get("additional_sections")
    if isinstance(additional, list):  # empty list is a deliberate "drop them all" signal, not "no response"
        original_by_key = {section.key: section for section in original.additional_sections}
        merged_additional = []
        for item in additional:
            if not isinstance(item, dict):
                continue
            original_section = original_by_key.get(item.get("key", ""))
            if original_section is None:
                continue  # never accept a key the model invented -- not in scraped.json
            merged_additional.append(
                AdditionalSection(
                    key=original_section.key,
                    title=item.get("title") or original_section.title,
                    body=item.get("body", ""),
                    items=item.get("items") or [],
                    images=original_section.images,
                )
            )
        merged.additional_sections = merged_additional

    return merged
