"""Structured, parser-backed tools for the SEO agent (seo_agent.py).

Why these exist: the SEO pass runs on HTML that earlier code steps have
already re-serialized with BeautifulSoup (`&amp;`, alphabetized-looking
attribute order such as `<meta content=".." name="description"/>`,
self-closing `/>`), while models write HTML the way they'd author it
(`&`, `name` first, no `/>`). An exact-string `edit_file` therefore missed
on nearly every call in real runs (seen 2026-10-06: 9 of 9 edits failed on
a 37 KB page, with the model re-reading the whole page between attempts).

These tools take *what* to change (a title, an image index + alt text, a
heading index + level) and do the HTML surgery with BeautifulSoup, so the
model never has to reproduce markup byte-for-byte. `get_page_outline`
gives the model a compact view of a page (a few KB) instead of the full
source. edit_file/read_file stay available as a fallback.

Every path goes through generation_tools._resolve_safe_path (sandboxed).
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from .generation_tools import SEO_TOOL_SCHEMAS, _resolve_safe_path, make_seo_tool_dispatch

_HEADING_RE = re.compile(r"^h[1-6]$")
_SKIP_TEXT_PARENTS = ("script", "style", "a", "button", "title", "head", "noscript")
OUTLINE_TEXT_CHARS = 1500
MAX_NEW_LINKS_PER_PAGE = 3


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_PATH = {"type": "string", "description": 'Page file, e.g. "index.html" or "about-us.html".'}

STRUCTURED_SEO_TOOL_SCHEMAS = [
    _fn(
        "get_page_outline",
        "Compact SEO view of one page: title, meta description, every heading (with index and level), "
        "every image (index, src, alt), every link (index, href, text), whether it has JSON-LD, and a "
        "short excerpt of the visible text. Use this instead of read_file.",
        {"path": _PATH},
        ["path"],
    ),
    _fn(
        "set_title",
        "Set the page's <title> text (plain text, no HTML).",
        {"path": _PATH, "title": {"type": "string"}},
        ["path", "title"],
    ),
    _fn(
        "set_meta_description",
        'Set (or add) the page\'s <meta name="description"> text (plain text, 120-160 characters).',
        {"path": _PATH, "description": {"type": "string"}},
        ["path", "description"],
    ),
    _fn(
        "set_image_alt",
        'Set the alt text of one image, by its index from get_page_outline. Use "" for purely decorative images.',
        {"path": _PATH, "image_index": {"type": "integer"}, "alt": {"type": "string"}},
        ["path", "image_index", "alt"],
    ),
    _fn(
        "set_heading_level",
        "Change one heading's level (e.g. h2 -> h1), by its index from get_page_outline. Only the tag "
        "name changes; classes, attributes and text are kept. Refused on pages where headings are "
        "styled by tag (the outline says heading_retag_safe: false).",
        {"path": _PATH, "heading_index": {"type": "integer"}, "level": {"type": "integer", "minimum": 1, "maximum": 6}},
        ["path", "heading_index", "level"],
    ),
    _fn(
        "update_link",
        "Change one link's href and/or its text, by its index from get_page_outline. Text can only be "
        "changed on links that contain plain text (no icons/images inside). Use for broken links and "
        'vague text like "click here".',
        {
            "path": _PATH,
            "link_index": {"type": "integer"},
            "href": {"type": "string", "description": "New href; omit to keep the current one."},
            "text": {"type": "string", "description": "New link text; omit to keep the current text."},
        },
        ["path", "link_index"],
    ),
    _fn(
        "link_phrase",
        "Turn an existing phrase in the page's body text into a link to another page (internal linking). "
        "The phrase must appear exactly once in a paragraph or list item that isn't already a link. "
        f"At most {MAX_NEW_LINKS_PER_PAGE} new links per page.",
        {"path": _PATH, "phrase": {"type": "string"}, "href": {"type": "string"}},
        ["path", "phrase", "href"],
    ),
    _fn(
        "add_structured_data",
        "Add one JSON-LD block (schema.org) to the page's <head>. Pass the JSON object as a string. "
        "Replaces an existing block with the same @type. Use only facts from the blueprint.",
        {"path": _PATH, "json_ld": {"type": "string"}},
        ["path", "json_ld"],
    ),
]

# Outline/structured tools first so the model reaches for them before the
# raw-text fallbacks.
ALL_SEO_TOOL_SCHEMAS = STRUCTURED_SEO_TOOL_SCHEMAS + SEO_TOOL_SCHEMAS


class _Page:
    def __init__(self, sandbox_root: Path, path: str, locked: set[str]):
        if path in locked:
            raise PermissionError(f"{path} is locked and cannot be changed.")
        self.path = path
        self.file = _resolve_safe_path(sandbox_root, path)
        if not self.file.is_file() or self.file.suffix.lower() not in (".html", ".htm"):
            raise FileNotFoundError(f"no such page: {path}")
        self.soup = BeautifulSoup(self.file.read_text(encoding="utf-8"), "lxml")

    def head(self) -> Tag:
        head = self.soup.find("head")
        if head is None:
            head = self.soup.new_tag("head")
            (self.soup.find("html") or self.soup).insert(0, head)
        return head

    def headings(self) -> list[Tag]:
        return self.soup.find_all(_HEADING_RE)

    def images(self) -> list[Tag]:
        return self.soup.find_all("img")

    def links(self) -> list[Tag]:
        return self.soup.find_all("a")

    def save(self) -> None:
        self.file.write_text(str(self.soup), encoding="utf-8")


def _text(tag: Tag, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_page_outline(
    sandbox_root: Path, path: str, retag_unsafe_pages: set[str], text_chars: int = OUTLINE_TEXT_CHARS
) -> dict:
    """Compact SEO view of one page -- what get_page_outline returns, and
    what seo_agent embeds for every page in the first message so the agent
    can start editing without spending steps on reads."""
    page = _Page(sandbox_root, path, set())
    description = page.soup.find("meta", attrs={"name": "description"})
    main = page.soup.find("main") or page.soup.body or page.soup
    return {
        "path": path,
        "title": page.soup.title.get_text(strip=True) if page.soup.title else "",
        "meta_description": (description.get("content") or "") if description else "",
        "heading_retag_safe": path not in retag_unsafe_pages,
        "headings": [{"index": i, "level": int(h.name[1]), "text": _text(h)} for i, h in enumerate(page.headings())],
        "images": [{"index": i, "src": img.get("src", ""), "alt": img.get("alt")} for i, img in enumerate(page.images())],
        "links": [{"index": i, "href": a.get("href", ""), "text": _text(a, 60)} for i, a in enumerate(page.links())],
        "has_structured_data": bool(page.soup.find("script", attrs={"type": "application/ld+json"})),
        "text_excerpt": _text(main, text_chars),
    }


def make_structured_seo_dispatch(
    sandbox_root: Path,
    *,
    locked_files: set[str] | None = None,
    retag_unsafe_pages: set[str] | None = None,
) -> dict:
    """Structured SEO tools + the edit_file/read_file/list_files/write_file
    fallbacks from generation_tools.make_seo_tool_dispatch. Tool errors come
    back as "Error: ..." strings (so the agent can correct itself);
    GenerationError (sandbox escape) still raises, as in every dispatch."""
    sandbox_root = sandbox_root.resolve()
    locked = set(locked_files or ())
    unsafe = set(retag_unsafe_pages or ())
    new_links: dict[str, int] = {}
    dispatch = make_seo_tool_dispatch(sandbox_root, locked_files=locked)

    def _guard(fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (PermissionError, FileNotFoundError, ValueError, IndexError) as exc:
                return f"Error: {exc}"

        return wrapper

    def get_page_outline(path: str) -> str:
        return json.dumps(build_page_outline(sandbox_root, path, unsafe), ensure_ascii=False)

    def set_title(path: str, title: str) -> str:
        page = _Page(sandbox_root, path, locked)
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        if page.soup.title is None:
            tag = page.soup.new_tag("title")
            page.head().insert(0, tag)
        page.soup.title.string = title
        page.save()
        return f"Title of {path} set ({len(title)} chars)"

    def set_meta_description(path: str, description: str) -> str:
        page = _Page(sandbox_root, path, locked)
        description = re.sub(r"\s+", " ", description).strip()
        if not description:
            raise ValueError("description must not be empty")
        tag = page.soup.find("meta", attrs={"name": "description"})
        if tag is None:
            tag = page.soup.new_tag("meta", attrs={"name": "description"})
            title = page.soup.title
            if title is not None:
                title.insert_after(tag)
            else:
                page.head().append(tag)
        tag["content"] = description
        page.save()
        return f"Meta description of {path} set ({len(description)} chars)"

    def set_image_alt(path: str, image_index: int, alt: str) -> str:
        page = _Page(sandbox_root, path, locked)
        images = page.images()
        if not 0 <= image_index < len(images):
            raise IndexError(f"{path} has {len(images)} image(s); index {image_index} doesn't exist")
        images[image_index]["alt"] = alt.strip()
        page.save()
        return f"Alt text of image {image_index} on {path} set"

    def set_heading_level(path: str, heading_index: int, level: int) -> str:
        if path in unsafe:
            raise PermissionError(
                f"headings on {path} are styled by tag, so changing their level would change the design -- leave them"
            )
        if not 1 <= int(level) <= 6:
            raise ValueError("level must be 1-6")
        page = _Page(sandbox_root, path, locked)
        headings = page.headings()
        if not 0 <= heading_index < len(headings):
            raise IndexError(f"{path} has {len(headings)} heading(s); index {heading_index} doesn't exist")
        heading = headings[heading_index]
        old = heading.name
        heading.name = f"h{int(level)}"
        page.save()
        return f"Heading {heading_index} on {path} changed from {old} to {heading.name}"

    def update_link(path: str, link_index: int, href: str | None = None, text: str | None = None) -> str:
        page = _Page(sandbox_root, path, locked)
        links = page.links()
        if not 0 <= link_index < len(links):
            raise IndexError(f"{path} has {len(links)} link(s); index {link_index} doesn't exist")
        link = links[link_index]
        if href is None and text is None:
            raise ValueError("pass href and/or text")
        if href is not None:
            link["href"] = href.strip()
        if text is not None:
            if any(isinstance(child, Tag) for child in link.children):
                raise ValueError("this link contains icons/images -- only its href can be changed")
            link.string = text.strip()
        page.save()
        return f"Link {link_index} on {path} updated"

    def link_phrase(path: str, phrase: str, href: str) -> str:
        if new_links.get(path, 0) >= MAX_NEW_LINKS_PER_PAGE:
            raise ValueError(f"already added {MAX_NEW_LINKS_PER_PAGE} new links to {path}")
        page = _Page(sandbox_root, path, locked)
        phrase = phrase.strip()
        if len(phrase) < 3:
            raise ValueError("phrase too short")
        matches = []
        for node in page.soup.find_all(string=True):
            if type(node) is not NavigableString or phrase not in node:
                continue  # skips comments/CDATA (NavigableString subclasses) too
            if any(parent.name in _SKIP_TEXT_PARENTS for parent in node.parents):
                continue
            if node.find_parent(["p", "li"]) is None:
                continue
            matches.append(node)
        occurrences = sum(str(node).count(phrase) for node in matches)
        if occurrences != 1:
            raise ValueError(
                f'"{phrase}" appears {occurrences} time(s) in linkable body text on {path} -- it must appear exactly once'
            )
        node = matches[0]
        before, after = str(node).split(phrase, 1)
        anchor = page.soup.new_tag("a", href=href.strip())
        anchor.string = phrase
        node.replace_with(before, anchor, after)
        page.save()
        new_links[path] = new_links.get(path, 0) + 1
        return f'Linked "{phrase}" on {path} to {href}'

    def add_structured_data(path: str, json_ld: str) -> str:
        page = _Page(sandbox_root, path, locked)
        try:
            data = json.loads(json_ld)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"json_ld is not valid JSON: {exc}") from exc
        if not isinstance(data, (dict, list)):
            raise ValueError("json_ld must be a JSON object (or a list of objects)")
        new_type = data.get("@type") if isinstance(data, dict) else None
        for existing in page.soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                existing_data = json.loads(existing.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            if new_type and isinstance(existing_data, dict) and existing_data.get("@type") == new_type:
                existing.decompose()
        script = page.soup.new_tag("script", attrs={"type": "application/ld+json"})
        script.string = json.dumps(data, ensure_ascii=False, indent=2)
        page.head().append(script)
        page.save()
        return f"Structured data{f' ({new_type})' if new_type else ''} added to {path}"

    def _site_pages() -> list[str]:
        return sorted(p.name for p in sandbox_root.glob("*.htm*"))

    def _locate(path: str) -> tuple[str, str]:
        """Models assume a project layout (seen: "public/index.html"). Every
        page lives at the top level of this workspace, so an unknown path
        whose filename exists there is mapped to it (with a note, so the
        model learns). The sandbox check still runs on the result."""
        requested = (path or "").strip()
        if (sandbox_root / requested.lstrip("/\\")).exists():
            return requested, ""
        name = Path(requested.replace("\\", "/")).name
        if name and (sandbox_root / name).is_file():
            return name, f"(note: '{requested}' doesn't exist -- used '{name}'; all pages are at the top level) "
        return requested, ""

    def _with_located_path(fn):
        def wrapper(*args, **kwargs):
            if "path" in kwargs:
                kwargs["path"], note = _locate(kwargs["path"])
            elif args:
                located, note = _locate(args[0])
                args = (located, *args[1:])
            else:
                note = ""
            result = fn(*args, **kwargs)
            if isinstance(result, str) and (result.startswith("Error") or result.startswith("No such file")):
                if "no such" in result.lower() or "doesn't exist" in result.lower():
                    result += f" -- the site's pages are: {', '.join(_site_pages())} (all at the top level, no folders)"
            return note + result if isinstance(result, str) else result

        return wrapper

    for name in ("read_file", "edit_file", "write_file"):
        dispatch[name] = _with_located_path(dispatch[name])

    for name, fn in (
        ("get_page_outline", get_page_outline),
        ("set_title", set_title),
        ("set_meta_description", set_meta_description),
        ("set_image_alt", set_image_alt),
        ("set_heading_level", set_heading_level),
        ("update_link", update_link),
        ("link_phrase", link_phrase),
        ("add_structured_data", add_structured_data),
    ):
        dispatch[name] = _with_located_path(_guard(fn))
    return dispatch
