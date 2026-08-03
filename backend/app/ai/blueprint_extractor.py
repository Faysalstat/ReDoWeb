import json
import re
from pathlib import Path
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from .errors import BlueprintExtractionError, OpenRouterError
from .openrouter_client import vision_json_chat

VISION_SYSTEM_PROMPT = (
    "You are a brand analyst. You will be shown a website's logo and/or "
    "representative images. Respond with ONLY a JSON object (no prose, no "
    "markdown fences) matching this exact shape: "
    '{"site_name": string, "colors": {"primary": "#rrggbb", "secondary": '
    '"#rrggbb", "accent": "#rrggbb"}, "fonts": {"heading": string, "body": '
    'string}, "tone": string}. Infer fonts as common web-safe or Google '
    "Font family names that visually match the image style if you cannot "
    "read exact font names. Keep tone to one short phrase (e.g. 'warm and "
    "friendly', 'corporate and minimal')."
)

DEFAULT_COLORS = {"primary": "#333333", "secondary": "#f5f5f5", "accent": "#0066cc"}
DEFAULT_FONTS = {"heading": "Inter", "body": "Inter"}
MAX_PARAGRAPHS_PER_PAGE = 20


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
    hero_assets = _pick_hero_images(assets_meta, logo_asset, limit=2)

    image_assets = ([logo_asset] if logo_asset else []) + hero_assets
    image_paths = [project_root / a["storage_path"] for a in image_assets]

    if image_paths:
        try:
            brand, usage = vision_json_chat(
                VISION_SYSTEM_PROMPT,
                f"Business name guess from page title: {site_name_guess or 'unknown'}. "
                "Analyze the attached logo/brand images and return the JSON described.",
                image_paths,
            )
        except OpenRouterError:
            raise
    else:
        brand = {}
        usage = {}

    colors = {**DEFAULT_COLORS, **(brand.get("colors") or {})}
    fonts = {**DEFAULT_FONTS, **(brand.get("fonts") or {})}

    frontmatter = {
        "site_name": brand.get("site_name") or site_name_guess or "Untitled Business",
        "colors": colors,
        "logo": logo_asset["storage_path"] if logo_asset else None,
        "fonts": fonts,
    }
    if brand.get("tone"):
        frontmatter["tone"] = brand["tone"]

    body = _build_markdown_body(pages_content)
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
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
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


def _pick_hero_images(assets: list[dict], logo_asset: dict | None, limit: int) -> list[dict]:
    logo_url = logo_asset["original_url"] if logo_asset else None
    hero = [a for a in assets if a["asset_type"] == "image" and a["original_url"] != logo_url]
    return hero[:limit]


def _build_markdown_body(pages_content: list[tuple[str, dict]]) -> str:
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

    return "\n".join(lines).strip() + "\n"


def _render_design_md(frontmatter: dict, body: str) -> str:
    front = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{front}\n---\n\n{body}"
