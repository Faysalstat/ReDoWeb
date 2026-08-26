import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from .color_extraction import extract_colors_from_css, extract_colors_from_image, gather_css_text
from .errors import BlueprintExtractionError, OpenRouterError
from .openrouter_client import vision_json_chat

BRAND_REVIEW_SYSTEM_PROMPT = (
    "You are a brand analyst reviewing scraped website data. You may be shown "
    "the site's logo image and a business-name guess scraped from the page "
    "title. Correct the guess only if the logo clearly shows a different or "
    "better-formatted name; otherwise leave it unchanged. Infer heading/body "
    "font families that visually match the logo's style (real web-safe or "
    "Google Font names, not the literal wordmark font). Infer an overall "
    "tone in one short phrase (e.g. 'warm and friendly', 'corporate and "
    "minimal'). If the logo gives no useful signal for a field, omit that "
    "field.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown fences) in this "
    "exact shape:\n"
    '{"site_name": string, "fonts": {"heading": string, "body": string}, '
    '"tone": string}'
)

CONTENT_GAP_SYSTEM_PROMPT = (
    "You are a content analyst reviewing scraped text content from a small "
    "business website. You'll be shown a digest of the site's scraped "
    "content (page titles, headings, opening lines, and whether contact "
    "info was found).\n\n"
    "Check the digest against these four section types: About/Value "
    "Proposition, Services/Features summary, Call To Action, FAQ. For any "
    "of these that the digest shows no real coverage of, draft a short "
    "replacement (one short paragraph, or 3-5 bullet points) in a tone "
    "matching the site's existing content -- but ONLY using facts already "
    "present in the digest. Do not invent services, claims, numbers, or "
    "names not already there. If a section is already covered, even "
    "briefly, do not draft a replacement for it.\n\n"
    "Absolute rule: never draft, imply, or fill in testimonials/customer "
    "quotes, statistics or numeric claims, pricing, credentials/awards/"
    "certifications, or contact details (email/phone/address). If the "
    "digest doesn't already contain real ones, leave them out entirely -- "
    "do not add placeholder or example versions of these under any "
    "circumstance.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown fences) in this "
    "exact shape:\n"
    '{"added_sections": [{"heading": string, "body": string}]}\n'
    '"added_sections" should only contain entries for section types you '
    "determined were genuinely missing per the rules above -- return an "
    "empty list if nothing needed drafting."
)

DEFAULT_COLORS = {"primary": "#333333", "secondary": "#f5f5f5", "accent": "#0066cc"}
DEFAULT_FONTS = {"heading": "Inter", "body": "Inter"}
MAX_PARAGRAPHS_PER_PAGE = 20
DIGEST_OPENING_WORDS = 20


def extract_blueprint(project_root: Path) -> dict:
    """Reads a crawled project's metadata.json + raw HTML/assets and writes
    project_root/blueprint/design.md -- a semi-structured blueprint with
    required YAML frontmatter (site_name, colors, logo, fonts) and a
    freeform markdown body (nav, per-page content, contact info).

    Raises BlueprintExtractionError for missing/invalid crawl data, and lets
    OpenRouterError bubble up from the vision call (both are definitive
    failures -- no retry logic in this synchronous slice).
    """
    metadata_path = project_root / "metadata.json"
    if not metadata_path.exists():
        raise BlueprintExtractionError(f"No crawl metadata found at {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    pages_meta = metadata.get("pages") or []
    assets_meta = metadata.get("assets") or []

    if not pages_meta:
        raise BlueprintExtractionError("Crawl metadata has no pages to extract from")

    pages_content = []
    for page in pages_meta:
        html = (project_root / page["storage_path"]).read_text(encoding="utf-8")
        pages_content.append((page["url"], _extract_page_content(html)))

    homepage_url = pages_meta[0]["url"]
    homepage_html = (project_root / pages_meta[0]["storage_path"]).read_text(encoding="utf-8")

    site_name_guess = _guess_site_name(homepage_html, pages_content[0][1])
    logo_asset = _guess_logo_asset(homepage_html, homepage_url, assets_meta)

    css_text = gather_css_text(homepage_html, homepage_url)
    colors = extract_colors_from_css(css_text)
    if colors is None and logo_asset:
        colors = extract_colors_from_image(project_root / logo_asset["storage_path"])
    if colors is None:
        colors = DEFAULT_COLORS

    image_paths = [project_root / logo_asset["storage_path"]] if logo_asset else []
    digest = _build_content_digest(pages_content)

    with ThreadPoolExecutor(max_workers=2) as executor:
        content_future = executor.submit(
            vision_json_chat, CONTENT_GAP_SYSTEM_PROMPT, digest, []
        )
        brand_future = (
            executor.submit(
                vision_json_chat,
                BRAND_REVIEW_SYSTEM_PROMPT,
                f"Business name guess from page title: {site_name_guess or 'unknown'}. "
                "Analyze the attached logo image and return the JSON described.",
                image_paths,
            )
            if image_paths
            else None
        )

        try:
            content_result, content_usage = content_future.result()
        except OpenRouterError:
            # Gap-filling is a purely additive enhancement -- degrade to "no
            # sections added" rather than failing the whole extraction over it.
            content_result, content_usage = {}, {}

        if brand_future is not None:
            brand, brand_usage = brand_future.result()  # propagates OpenRouterError, as before
        else:
            brand, brand_usage = {}, {}

    fonts = {**DEFAULT_FONTS, **(brand.get("fonts") or {})}

    frontmatter = {
        "site_name": brand.get("site_name") or site_name_guess or "Untitled Business",
        "colors": colors,
        "logo": logo_asset["storage_path"] if logo_asset else None,
        "fonts": fonts,
    }
    if brand.get("tone"):
        frontmatter["tone"] = brand["tone"]

    added_sections = content_result.get("added_sections") or []
    body = _build_markdown_body(pages_content, added_sections)
    design_md = _render_design_md(frontmatter, body)

    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    design_md_path = blueprint_dir / "design.md"
    design_md_path.write_text(design_md, encoding="utf-8")

    return {
        "design_md_path": design_md_path.relative_to(project_root).as_posix(),
        "frontmatter": frontmatter,
        "design_md": design_md,
        "usage": {
            "prompt_tokens": brand_usage.get("prompt_tokens", 0) + content_usage.get("prompt_tokens", 0),
            "completion_tokens": brand_usage.get("completion_tokens", 0)
            + content_usage.get("completion_tokens", 0),
        },
    }


def _extract_page_content(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.get_text(strip=True) if soup.title else None

    headings = []
    for level in range(1, 4):
        for tag in soup.find_all(f"h{level}"):
            text = tag.get_text(strip=True)
            if text:
                headings.append({"level": level, "text": text})

    nav_links = []
    nav_scope = soup.find("nav") or soup.find("header")
    if nav_scope:
        for anchor in nav_scope.find_all("a", href=True):
            label = anchor.get_text(strip=True)
            if label:
                nav_links.append({"label": label, "href": anchor["href"]})

    main_scope = soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in main_scope.find_all("p")]
    paragraphs = [p for p in paragraphs if p][:MAX_PARAGRAPHS_PER_PAGE]

    full_text = soup.get_text(" ", strip=True)
    email_match = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", full_text)
    phone_match = re.search(r"(\+?\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", full_text)

    return {
        "title": title,
        "headings": headings,
        "nav_links": nav_links,
        "paragraphs": paragraphs,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
    }


def _guess_site_name(homepage_html: str, homepage_content: dict) -> str | None:
    soup = BeautifulSoup(homepage_html, "lxml")
    og_site_name = soup.find("meta", property="og:site_name")
    if og_site_name and og_site_name.get("content"):
        return og_site_name["content"].strip()

    if homepage_content.get("title"):
        return re.split(r"[|\-–]", homepage_content["title"])[0].strip()

    if homepage_content.get("headings"):
        return homepage_content["headings"][0]["text"]

    return None


def _guess_logo_asset(homepage_html: str, homepage_url: str, assets: list[dict]) -> dict | None:
    soup = BeautifulSoup(homepage_html, "lxml")
    assets_by_url = {a["original_url"]: a for a in assets}

    for img in soup.find_all("img"):
        haystack = " ".join(
            filter(
                None,
                [
                    img.get("alt", ""),
                    " ".join(img.get("class", [])),
                    img.get("id", ""),
                    img.get("src", ""),
                ],
            )
        ).lower()
        if "logo" in haystack:
            src = img.get("src")
            if src:
                absolute = urljoin(homepage_url, src)
                if absolute in assets_by_url:
                    return assets_by_url[absolute]

    for asset in assets:
        if asset["asset_type"] == "image":
            return asset

    return None


def _build_content_digest(pages_content: list[tuple[str, dict]]) -> str:
    """Compact, cheap-to-send summary of the already-scraped content for the
    content-gap review call -- page titles, heading text, a short opening
    snippet, and contact-info presence, NOT the full paragraph text. Kept
    small on purpose since this is sent as live (uncached) tokens."""
    blocks: list[str] = []
    for url, content in pages_content:
        lines = [f"Page: {content['title'] or url} ({url})"]
        if content["headings"]:
            lines.append("Headings: " + " | ".join(h["text"] for h in content["headings"]))
        if content["paragraphs"]:
            words = content["paragraphs"][0].split()
            snippet = " ".join(words[:DIGEST_OPENING_WORDS])
            if len(words) > DIGEST_OPENING_WORDS:
                snippet += "..."
            lines.append(f'Opening line: "{snippet}"')
        has_contact = bool(content["email"] or content["phone"])
        lines.append(f"Contact info found: {'yes' if has_contact else 'no'}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _build_markdown_body(pages_content: list[tuple[str, dict]], added_sections: list[dict] | None = None) -> str:
    lines: list[str] = []

    home_url, home_content = pages_content[0]
    if home_content["nav_links"]:
        lines.append("## Navigation")
        for link in home_content["nav_links"]:
            lines.append(f"- {link['label']} ({link['href']})")
        lines.append("")

    for index, (url, content) in enumerate(pages_content):
        page_title = "Home Page" if index == 0 else (content["title"] or url)
        lines.append(f"## {page_title}")

        if content["headings"]:
            lines.append("### Hero")
            lines.append(f"Headline: {content['headings'][0]['text']}")
            if content["paragraphs"]:
                lines.append(f"Subheading: {content['paragraphs'][0]}")
            lines.append("")

            if len(content["headings"]) > 1:
                lines.append("### Sections")
                for heading in content["headings"][1:]:
                    lines.append(f"- {heading['text']}")
                lines.append("")

        if content["paragraphs"]:
            lines.append("### Content")
            for paragraph in content["paragraphs"]:
                lines.append(paragraph)
            lines.append("")

        if content["email"] or content["phone"]:
            lines.append("### Contact")
            if content["email"]:
                lines.append(f"- Email: {content['email']}")
            if content["phone"]:
                lines.append(f"- Phone: {content['phone']}")
            lines.append("")

        if index == 0:
            for section in added_sections or []:
                heading = section.get("heading")
                text = section.get("body")
                if not heading or not text:
                    continue
                lines.append("<!-- ai-drafted -->")
                lines.append(f"### {heading}")
                lines.append(text)
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def _render_design_md(frontmatter: dict, body: str) -> str:
    front = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{front}\n---\n\n{body}"
