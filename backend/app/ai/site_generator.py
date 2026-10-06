import hashlib
import json
import random
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..config import get_settings
from ..services import tier_service
from .blueprint_legacy_compat import render_design_md_compat
from .blueprint_schema import BlueprintDocument
from .errors import GenerationError, IterationLimitError, OpenRouterError
from .generation_tools import TOOL_SCHEMAS, make_tool_dispatch
from .openrouter_client import chat_completion
from .postprocess import parse_frontmatter, postprocess_output, site_origin_from_url
from .site_consistency import (
    enforce_shared_head,
    guard_appended_css,
    rewrite_internal_links,
    shared_shell_excerpt,
    sync_site_chrome,
)

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

TECH_CONSTRAINTS = """

---

IMPORTANT project-specific constraints (these override anything above that conflicts):
- There is no existing codebase and no build tooling. Do NOT scaffold React, Next.js, Vue, or any framework/bundler.
- Build a plain static website: one .html file per page, a single shared style.css, and an optional shared script.js. Use the write_file tool for every file you create.
- You may use Tailwind CSS via its CDN script tag, Bootstrap via its CDN link, or hand-written CSS in style.css -- whichever best expresses the design system above. Do not run any build step; everything must work as plain static files.
- An images/ folder already exists in the output directory with the site's real logo and photos, downloaded from the original site. Do not invent placeholder images -- reference only the exact filenames listed in the user message, e.g. <img src="images/...">.
- There is no user to ask questions of -- the content below is your complete brief; just build the site.
- When completely finished, respond with a final plain-text summary of the pages and files you created, and do not request any more tool calls.
- Build ONLY the home page for this run -- a single index.html plus style.css (and an optional script.js). If the content below describes more than one page, use only the home page's content; ignore the rest (additional pages are a separate, later generation pass, not part of this run).
"""

FULL_SITE_TECH_CONSTRAINTS = """

---

IMPORTANT project-specific constraints (these override anything above that conflicts):
- There is no existing codebase and no build tooling. Do NOT scaffold React, Next.js, Vue, or any framework/bundler.
- index.html, style.css (and script.js / any other asset files, when the home page has them) already exist in this output directory and are the LIVE, already-generated, already-shown-to-the-user home page and design system -- copied here verbatim. index.html is READ-ONLY: calling write_file on it will fail with an error and do nothing. style.css, script.js and every other existing .css/.js file are APPEND-ONLY: calling write_file on them never replaces their contents, it only adds your new content to the end -- so never re-paste a whole file, only write what a new page actually needs beyond what's already there.
- New CSS rules must use NEW component class names only. Rules that target bare elements (body, h1, a, section, ...), :root, *, or any selector already defined in style.css are automatically removed after this run -- they would change the look of the existing pages.
- Build every other page listed in the user message below (NOT the home page, which is already done) as its own .html file, using the exact filename given for each. Every page's <head> assets, nav/header, and footer must match index.html's exactly -- the user message includes them verbatim; copy them as-is, then reuse index.html's markup structure/classes for the page body so the whole site looks like one consistent design.
- You may use Tailwind CSS via its CDN script tag, Bootstrap via its CDN link, or hand-written CSS in style.css -- whichever index.html already uses (match it, don't introduce a second approach).
- An images/ folder already exists in the output directory with the site's real logo and photos, downloaded from the original site. Do not invent placeholder images -- reference only the exact filenames listed in the user message.
- There is no user to ask questions of -- the content below is your complete brief; just build the pages.
- When completely finished with every page listed, respond with a final plain-text summary of the pages and files you created, and do not request any more tool calls.
"""

FULL_SITE_PAGES_PER_BATCH = 4


def _select_template(override: str | None = None, candidates: list[str] | None = None) -> Path:
    """Picks one of PROMPTS_DIR's static business_*.txt design-strategy
    files at random -- the sole generation strategy for every tier.

    `candidates`, when given, restricts the random choice to that set of
    filenames (the admin-enabled subset resolved by
    prompt_template_service.get_active_template_filenames -- this function
    stays DB-free per its existing contract, so the DB query happens one
    layer up in tasks_generate.py). `candidates=None` preserves the
    original "every file on disk" behavior exactly, for callers that don't
    pass it (debug routes, tests, generate_full_site's template_override
    path)."""
    if override:
        prompts_root = PROMPTS_DIR.resolve()
        template_path = (PROMPTS_DIR / override).resolve()
        if not template_path.is_relative_to(prompts_root) or not template_path.exists():
            raise GenerationError(f"Template not found: {override}")
        return template_path

    templates = sorted(PROMPTS_DIR.glob("*.txt"))
    if candidates is not None:
        allowed = set(candidates)
        templates = [t for t in templates if t.name in allowed]
    if not templates:
        raise GenerationError(f"No design-strategy templates found in {PROMPTS_DIR}")
    return random.choice(templates)


def _rmtree_with_retry(path: Path, attempts: int = 5, delay_seconds: float = 1.0) -> None:
    """Empties `path` (deletes everything inside it) rather than removing
    the directory object itself, then retries briefly on Windows
    PermissionError (WinError 32) for individual entries.

    On Windows, a file watcher (an editor, a search indexer, antivirus)
    commonly holds a directory handle open purely for change-notification
    purposes (ReadDirectoryChangesW) -- this blocks removing/renaming the
    directory itself but does NOT block creating, writing, or deleting
    files inside it. shutil.rmtree(path) fails on that outer handle even
    though every individual delete would succeed, so this clears contents
    one entry at a time (each with its own short retry) and leaves the
    directory in place instead of trying to remove it.
    """
    last_error: OSError | None = None
    for entry in path.iterdir():
        for attempt in range(attempts):
            try:
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(delay_seconds)
        if last_error is not None:
            raise last_error


def generate_site(
    project_root: Path,
    tier_key: str,
    template_override: str | None = None,
    generation_model: str | None = None,
    candidate_templates: list[str] | None = None,
) -> dict:
    """Builds the tier's home page from project_root/blueprint/design.md --
    which the blueprint pipeline (blueprint_pipeline.run_blueprint_pipeline)
    renders from the reviewed blueprint.json via blueprint_legacy_compat, so
    this already reflects the structured-JSON pipeline's output without
    needing to read blueprint.json directly here. Scoped to one page (the
    home page) per docs/blueprint-json-pipeline-plan.md -- additional pages
    are a separate, later generation pass, not built by this function.

    Every tier uses the same template-based strategy (removed 2026-09-16,
    at the user's explicit request, after the AI-generated recipe-anchor/
    design-system path -- previously used by every tier but "premium" --
    caused real confusion: a project generating only one tier still paid
    for the design-system AI call, and its resolved recipe_anchor surfaced
    in places that made it look like it had been used for generation when
    it hadn't been). One of PROMPTS_DIR's static hand-authored
    business_*.txt files is picked at random (or via `template_override`,
    path-traversal-checked -- real callers never pass this; it exists for
    repeatable manual testing of one specific template) + TECH_CONSTRAINTS.

    `generation_model` is the resolved OpenRouter model id for this run's
    agent loop -- real callers (tasks_generate.py) resolve it per-tier via
    model_config_service.get_generation_model() (DB-backed, swappable
    without a rebuild) and pass it in; this function stays DB-free and
    falls back to config.py's static default when it's omitted (debug
    routes rely on that default).

    `candidate_templates`, similarly, is the admin-enabled filename subset
    resolved by tasks_generate.py via
    prompt_template_service.get_active_template_filenames() -- omitted
    (None), every file in PROMPTS_DIR is a candidate, same as before this
    admin control existed.
    """
    if not tier_service.is_tier_enabled(tier_key):
        raise GenerationError(f"Tier '{tier_key}' is not currently enabled")

    design_md_path = project_root / "blueprint" / "design.md"
    if not design_md_path.exists():
        raise GenerationError("No blueprint found for this project -- run blueprint extraction first")
    design_md = design_md_path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(design_md)

    metadata = json.loads((project_root / "metadata.json").read_text(encoding="utf-8"))
    assets = metadata.get("assets") or []
    # The real domain the user submitted -- see postprocess.site_origin_from_url.
    site_origin = site_origin_from_url(metadata.get("source_url"))

    settings = get_settings()
    generation_model = generation_model or settings.generation_model

    output_dir = project_root / "generated" / tier_key
    if output_dir.exists():
        _rmtree_with_retry(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_names = _copy_images(project_root, output_dir, assets)
    (output_dir / "design.md").write_text(design_md, encoding="utf-8")
    blueprint_json_path = project_root / "blueprint" / "blueprint.json"
    if blueprint_json_path.exists():
        (output_dir / "blueprint.json").write_text(
            blueprint_json_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    template_path = _select_template(template_override, candidate_templates)
    system_prompt = template_path.read_text(encoding="utf-8") + TECH_CONSTRAINTS
    strategy_used = template_path.name

    user_message = _build_user_message(design_md, image_names)

    dispatch = make_tool_dispatch(output_dir)
    trace_path = output_dir / "_debug_trace.json"
    summary_text, total_usage, iterations_used = _run_agent_loop(
        settings, generation_model, system_prompt, user_message, dispatch, trace_path=trace_path
    )

    postprocess_report = postprocess_output(output_dir, frontmatter, site_origin=site_origin)

    written_files = sorted(
        p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file()
    )

    return {
        "tier": tier_key,
        "postprocess": postprocess_report,
        "template_used": strategy_used,
        "output_dir": output_dir.relative_to(project_root).as_posix(),
        "files": written_files,
        "summary": summary_text,
        "usage": total_usage,
        "iterations": iterations_used,
        "model": generation_model,
        "site_origin": site_origin,
    }


_SLUG_UNSAFE_RE = re.compile(r"[^a-z0-9]+")
_RESERVED_SLUGS = {"index", "sitemap", "robots", "llms", "style", "script"}


def _page_output_filename(index: int, page_url: str) -> str:
    """index 0 -> "index.html" (the already-generated, locked home page);
    index N>0 -> a clean, SEO-friendly slug from the crawled URL's path
    ("https://x.com/about-us/" -> "about-us.html", "/services/web" ->
    "services-web.html"). Only [a-z0-9-] ever reaches the filename, so a
    hostile crawled URL can't produce a path-traversal or odd filename;
    falls back to "page-{N}.html" when the path yields no usable slug.
    Collisions between pages are resolved by _page_output_filenames."""
    if index == 0:
        return "index.html"
    try:
        path = unquote(urlsplit(page_url).path)
    except ValueError:
        path = ""
    path = re.sub(r"\.(html?|php|aspx?|jsp)$", "", path.strip("/"), flags=re.IGNORECASE)
    slug = _SLUG_UNSAFE_RE.sub("-", path.lower()).strip("-")[:60].strip("-")
    if not slug or slug in _RESERVED_SLUGS:
        return f"page-{index}.html"
    return f"{slug}.html"


def _page_output_filenames(page_urls: list[str]) -> list[str]:
    """_page_output_filename for every page, with collisions (two crawled
    URLs slugging to the same name) disambiguated by a -2/-3 suffix in crawl
    order."""
    used: set[str] = set()
    names: list[str] = []
    for index, url in enumerate(page_urls):
        name = _page_output_filename(index, url)
        if name in used:
            stem = name[: -len(".html")]
            n = 2
            while f"{stem}-{n}.html" in used:
                n += 1
            name = f"{stem}-{n}.html"
        used.add(name)
        names.append(name)
    return names


def _build_full_site_batch_message(
    batch_design_md: str,
    filename_map: str,
    batch_filenames: list[str],
    image_names: list[str],
    shared_shell: str = "",
) -> str:
    image_list = "\n".join(f"- images/{name}" for name in image_names) or "(no images available)"
    pages_list = "\n".join(f"- {name}" for name in batch_filenames)
    shell_block = (
        "Shared markup from index.html that EVERY page must reuse exactly "
        "(head assets, nav/header, footer):\n"
        f"{shared_shell}\n\n"
        if shared_shell
        else ""
    )
    return (
        f"{shell_block}"
        "Full site page -> filename map (use this for every nav link you "
        "write, including links to pages outside this batch -- they'll be "
        "built in a later batch but must still be linked correctly now):\n"
        f"{filename_map}\n\n"
        f"Build ONLY these pages in this batch:\n{pages_list}\n\n"
        "Business content and brand blueprint (YAML frontmatter + page "
        "content). The 'Home Page' section below is reference only -- "
        "index.html is already built and locked, do not rebuild it; every "
        "other section below is a page you must build this batch:\n\n"
        f"{batch_design_md}\n\n"
        "Available image files already in the output directory's images/ "
        f"folder (reference these exact paths, do not invent new ones):\n{image_list}\n\n"
        "Build these pages now."
    )


def generate_full_site(
    project_root: Path,
    tier_key: str,
    template_override: str | None = None,
    generation_model: str | None = None,
) -> dict:
    """Builds every crawled page (not just the home page) into
    generated/{tier}/full/ -- a sibling of generated/{tier}/, so the
    already-served preview output is never touched. Reads blueprint.json
    directly (by this point already merged to include every crawled page --
    see workers/tasks_full_site.py) since it needs the page list to build
    the filename map and per-batch design.md excerpts, but the model is
    still only ever shown design.md-rendered text (via
    blueprint_legacy_compat.render_design_md_compat), exactly like
    generate_site().

    `template_override` is REQUIRED (raises if omitted) -- this never
    re-rolls _select_template()'s random choice; real callers always pass
    the original preview run's `template_used` so the additional pages are
    built with the same design-strategy prompt as the already-shown home
    page.

    Style continuity is enforced in layers (see
    docs/seo-agent-and-buy-flow-plan.md, "Design consistency", D1-D6):
    physically, by copying every preview file (index.html, style.css,
    script.js, ...) into the new output directory before generation starts;
    at the tool layer, by making index.html unwritable and every copied
    .css/.js append-only (generation_tools.make_tool_dispatch's
    locked_files/append_only_files); in the prompt, by handing each batch
    index.html's head assets + nav/footer verbatim (shared_shell_excerpt);
    and afterwards, by site_consistency's deterministic guards (local link
    rewrite, shared head assets, nav/footer sync, appended-CSS guard).
    The system prompt (FULL_SITE_TECH_CONSTRAINTS) explains this to the
    model, but nothing relies on the model obeying it voluntarily.

    Generated in batches of FULL_SITE_PAGES_PER_BATCH pages per agent-loop
    call, not one call for every remaining page -- a full ~19-page crawl's
    worth of content and page requirements in a single prompt risks the
    same truncation/iteration-exhaustion failure mode CLAUDE.md documents
    for an undersized max_tokens; each batch call stays close to
    generate_site()'s single-page prompt size instead. Batches share the
    same output_dir and tool dispatch, so a later batch can read_file/
    list_files an earlier batch's pages to keep nav/markup consistent.
    """
    if not tier_service.is_tier_enabled(tier_key):
        raise GenerationError(f"Tier '{tier_key}' is not currently enabled")
    if not template_override:
        raise GenerationError("generate_full_site requires the preview run's template_used")

    blueprint_json_path = project_root / "blueprint" / "blueprint.json"
    if not blueprint_json_path.exists():
        raise GenerationError("No blueprint found for this project -- run blueprint extraction first")
    blueprint = BlueprintDocument.model_validate(json.loads(blueprint_json_path.read_text(encoding="utf-8")))
    if len(blueprint.pages) < 2:
        raise GenerationError("generate_full_site requires more than one reviewed page")

    design_md_path = project_root / "blueprint" / "design.md"
    design_md = (
        design_md_path.read_text(encoding="utf-8") if design_md_path.exists() else render_design_md_compat(blueprint)
    )
    frontmatter = parse_frontmatter(design_md)

    metadata = json.loads((project_root / "metadata.json").read_text(encoding="utf-8"))
    assets = metadata.get("assets") or []
    # The real domain the user submitted -- see postprocess.site_origin_from_url.
    site_origin = site_origin_from_url(metadata.get("source_url"))

    settings = get_settings()
    generation_model = generation_model or settings.generation_model

    preview_dir = project_root / "generated" / tier_key
    output_dir = preview_dir / "full"
    if output_dir.exists():
        _rmtree_with_retry(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_files = _copy_preview_files(preview_dir, output_dir)
    if not (output_dir / "index.html").exists():
        raise GenerationError("No preview index.html found on disk to anchor the full-site design to")
    # D1: every copied stylesheet/script is append-only (so the home page's
    # own CSS/JS can never be replaced), every other copied file (index.html,
    # favicon, ...) is locked outright.
    append_only_files = {name for name in copied_files if name.lower().endswith((".css", ".js"))}
    append_only_files |= {"style.css", "script.js"}
    locked_files = {name for name in copied_files if name not in append_only_files} | {"index.html"}
    original_stylesheets = {
        name: (output_dir / name).read_text(encoding="utf-8")
        for name in copied_files
        if name.lower().endswith(".css")
    }
    shared_shell = shared_shell_excerpt((output_dir / "index.html").read_text(encoding="utf-8"))

    image_names = _copy_images(project_root, output_dir, assets)
    (output_dir / "design.md").write_text(design_md, encoding="utf-8")
    (output_dir / "blueprint.json").write_text(
        json.dumps(blueprint.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    template_path = _select_template(template_override)
    system_prompt = template_path.read_text(encoding="utf-8") + FULL_SITE_TECH_CONSTRAINTS
    strategy_used = template_path.name

    page_filenames = _page_output_filenames([page.page_url for page in blueprint.pages])
    filename_map = "\n".join(
        f"- {page.page_url} -> {filename}" for page, filename in zip(blueprint.pages, page_filenames)
    )

    dispatch = make_tool_dispatch(output_dir, locked_files=locked_files, append_only_files=append_only_files)

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    total_iterations = 0
    last_summary = ""

    home_page = blueprint.pages[0]
    remaining_indices = list(range(1, len(blueprint.pages)))
    for batch_number, batch_start in enumerate(range(0, len(remaining_indices), FULL_SITE_PAGES_PER_BATCH)):
        batch_indices = remaining_indices[batch_start : batch_start + FULL_SITE_PAGES_PER_BATCH]
        # home_page always occupies position 0 so blueprint_legacy_compat's
        # positional "index 0 == Home Page" labeling stays correct -- a
        # batch_doc built from ONLY the non-home pages would put a real
        # other page at position 0 and mislabel it "Home Page".
        batch_doc = BlueprintDocument(
            meta=blueprint.meta,
            navigation=blueprint.navigation,
            pages=[home_page] + [blueprint.pages[i] for i in batch_indices],
        )
        batch_design_md = render_design_md_compat(batch_doc)
        batch_filenames = [page_filenames[i] for i in batch_indices]

        user_message = _build_full_site_batch_message(
            batch_design_md, filename_map, batch_filenames, image_names, shared_shell
        )

        trace_path = output_dir / f"_debug_trace_batch_{batch_number}.json"
        summary_text, batch_usage, batch_iterations = _run_agent_loop(
            settings,
            generation_model,
            system_prompt,
            user_message,
            dispatch,
            trace_path=trace_path,
            required_files=tuple(batch_filenames),
        )
        total_usage["prompt_tokens"] += batch_usage["prompt_tokens"]
        total_usage["completion_tokens"] += batch_usage["completion_tokens"]
        total_iterations += batch_iterations
        last_summary = summary_text

    # Deterministic design-consistency pass (docs/seo-agent-and-buy-flow-plan.md,
    # D2/D4/D5 + breakage item 5a). Order matters: links are rewritten first
    # so the nav/footer copied by sync_site_chrome already points at the
    # local pages.
    consistency_report = {
        "links_rewritten": rewrite_internal_links(
            output_dir, [page.page_url for page in blueprint.pages], page_filenames
        ),
        "head_assets_added": enforce_shared_head(output_dir),
        "chrome_synced": sync_site_chrome(output_dir),
        "css_rules_stripped": [
            change
            for name, original in original_stylesheets.items()
            for change in guard_appended_css(output_dir / name, original)
        ],
    }

    postprocess_report = postprocess_output(output_dir, frontmatter, site_origin=site_origin)
    written_files = sorted(p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file())

    return {
        "tier": tier_key,
        "postprocess": postprocess_report,
        "template_used": strategy_used,
        "output_dir": output_dir.relative_to(project_root).as_posix(),
        "files": written_files,
        "summary": last_summary,
        "usage": total_usage,
        "iterations": total_iterations,
        "model": generation_model,
        "site_origin": site_origin,
        "consistency": consistency_report,
    }


# Preview-output entries that are never copied into full/ -- sibling build
# outputs, the separately-copied images folder, and files generate_full_site
# rewrites itself (design.md/blueprint.json) or regenerates (sitemap.xml).
_PREVIEW_COPY_SKIP_DIRS = {"full", "seo", "images"}
_PREVIEW_COPY_SKIP_FILES = {"design.md", "blueprint.json", "sitemap.xml"}


def _copy_preview_files(preview_dir: Path, output_dir: Path) -> list[str]:
    """D1: copies EVERY file the preview run produced (index.html,
    style.css, script.js, any extra CSS/JS/favicon) byte-for-byte into
    full/, not just index.html + style.css -- otherwise a page referencing
    script.js 404s, or the agent writes a new script.js that index.html then
    loads, changing the home page's behavior. Returns the copied files'
    relative posix paths."""
    copied: list[str] = []
    if not preview_dir.exists():
        return copied
    for src in sorted(preview_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(preview_dir)
        if len(rel.parts) > 1 and rel.parts[0] in _PREVIEW_COPY_SKIP_DIRS:
            continue
        if rel.name in _PREVIEW_COPY_SKIP_FILES or rel.name.startswith("_debug_trace"):
            continue
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        copied.append(rel.as_posix())
    return copied


# Read-style tools whose latest result per path can be kept in context
# (keep_latest_reads) -- see _compact_resolved_tool_turns.
_READ_TOOLS = ("read_file", "get_page_outline")


def _latest_read_message_ids(messages: list[dict], before_index: int) -> set[int]:
    """id()s of the most recent read_file/get_page_outline result message
    for each path in messages[:before_index]."""
    call_paths: dict[str, str] = {}
    for message in messages[:before_index]:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            if fn.get("name") not in _READ_TOOLS:
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(args, dict) and args.get("path"):
                key = f"{fn['name']}:{str(args['path']).lstrip('./')}"
                call_paths[call.get("id")] = key
    latest: dict[str, int] = {}
    for message in messages[:before_index]:
        if message.get("role") == "tool" and message.get("tool_call_id") in call_paths:
            latest[call_paths[message["tool_call_id"]]] = id(message)
    return set(latest.values())


def _compact_resolved_tool_turns(
    messages: list[dict], before_index: int, keep_latest_reads: bool = False
) -> None:
    """Shrinks large read_file/list_files results in messages[:before_index]
    down to short summaries, in place, leaving assistant tool_calls
    (including write_file's) completely untouched.

    write_file calls used to have their arguments rewritten to a compacted
    placeholder here. That was removed: regardless of the placeholder's
    exact shape (tried both a fake {"path","content"} object and a
    {"note": ...} marker), some models will echo their own visible history
    back verbatim as a new tool call -- so the moment history contains
    ANYTHING that looks like a prior write_file call, it risks being
    replayed and failing dispatch, burning the iteration budget on repeats
    of the identical error. Leaving real write_file calls (and their
    genuinely small "Wrote N characters..." results) alone in history
    avoids giving the model anything synthetic to latch onto; only
    read_file/list_files results are compacted here, since those are
    unmodified data the model retrieved, not calls it might reissue.

    Messages are mutated in place and never removed or reordered, so every
    assistant message's tool_calls keep their matching role:"tool" results
    immediately after them -- required by the OpenAI-style tool-calling
    wire format this loop speaks to OpenRouter.
    """
    # keep_latest_reads: an edit-in-place agent (the SEO pass) has to quote
    # the current file text exactly, so the most recent read of each file
    # stays verbatim; only superseded reads are compacted. Seen 2026-10-06:
    # with every read compacted, the model re-read a 37 KB page six times
    # and still wrote every edit from memory, so none of them matched.
    keep = _latest_read_message_ids(messages, before_index) if keep_latest_reads else set()
    for message in messages[:before_index]:
        if message.get("role") != "tool" or id(message) in keep:
            continue
        content = message.get("content") or ""
        if len(content) > 300 and not content.startswith("(compacted"):
            message["content"] = (
                f"(compacted -- {len(content)} chars previously returned here; "
                "call the tool again if you need the current content)"
            )


# Per TECH_CONSTRAINTS: a single index.html plus a single shared style.css
# for this run's one page -- script.js is explicitly optional there, so it
# is deliberately not checked here.
REQUIRED_OUTPUT_FILES = ("index.html", "style.css")


def _missing_required_output_files(
    trace_path: Path | None, required_files: tuple[str, ...] = REQUIRED_OUTPUT_FILES
) -> list[str]:
    """Checks `required_files` (REQUIRED_OUTPUT_FILES by default) against
    the actual output directory (trace_path.parent -- trace_path is always
    output_dir/_debug_trace.json, see generate_site()/generate_full_site()).
    Returns [] (never blocking) when trace_path is None, since that only
    happens if a caller opts out of tracing."""
    if trace_path is None:
        return []
    output_dir = trace_path.parent
    return [name for name in required_files if not (output_dir / name).exists()]


def _run_agent_loop(
    settings,
    model_name: str,
    system_prompt: str,
    user_message: str,
    dispatch: dict,
    trace_path: Path | None = None,
    required_files: tuple[str, ...] = REQUIRED_OUTPUT_FILES,
    tool_schemas: list[dict] = TOOL_SCHEMAS,
    on_event: Callable[[dict], None] | None = None,
    keep_latest_reads: bool = False,
    max_iterations: int | None = None,
):
    """`on_event`, when given, is called with {"type": "iteration", ...} at
    the start of every model call and {"type": "tool", ...} after every
    executed tool call -- used for live progress/activity tracking (see
    seo_agent.run_seo_pass). It's observation only: an exception inside it
    is swallowed, never allowed to break the generation run."""

    def _emit(event: dict) -> None:
        if on_event is None:
            return
        try:
            on_event(event)
        except Exception:  # noqa: BLE001 -- progress tracking must never break generation
            pass

    caching_enabled = settings.generation_prompt_caching_enabled
    system_content: str | list[dict] = system_prompt
    user_content: str | list[dict] = user_message
    if caching_enabled:
        # The design-strategy template + TECH_CONSTRAINTS is the largest
        # static block in the request (2.4K-6K tokens) and is byte-identical
        # on every iteration -- this is the first and biggest cache
        # breakpoint, separate from the user-turn breakpoint below so both
        # get cached independently of each other.
        system_content = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        # design.md + image list are 100% static for the whole run, and this
        # is the last block of the static prefix (tools -> system -> this
        # message) -- caching it here covers the entire fixed portion of
        # every iteration's request in one breakpoint.
        user_content = [
            {
                "type": "text",
                "text": user_message,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    messages: list[dict] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    trace: list[dict] = []

    session_id = None
    if caching_enabled and trace_path is not None:
        # Stable per generation run (one project + tier) so OpenRouter's
        # sticky routing keeps every iteration on the same upstream
        # provider that holds the warm cache -- without this, cache hits
        # across the loop aren't guaranteed even with correct markers.
        session_id = hashlib.sha256(str(trace_path).encode("utf-8")).hexdigest()

    # Counts total occurrences of each distinct failure signature across the
    # whole run, NOT reset on an unrelated success -- a run that alternates
    # fail/fail/fail/succeed-on-something-irrelevant/fail/... never trips a
    # strictly-consecutive counter but is just as stuck, and would otherwise
    # burn the entire iteration budget without making real progress.
    failure_counts: dict[str, int] = {}

    def _flush_trace():
        if trace_path is not None:
            trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    max_iterations = max_iterations or settings.generation_max_iterations
    last_content = ""
    for iteration in range(1, max_iterations + 1):
        _emit({"type": "iteration", "iteration": iteration, "max_iterations": max_iterations})
        current_iter_start = len(messages)
        # Compact every prior iteration's resolved tool turns, but leave the
        # iteration we're about to append fully intact. This is pure local
        # context hygiene -- independent of whether OpenRouter's upstream
        # cache_control is honored, so it always runs even when
        # caching_enabled is off.
        _compact_resolved_tool_turns(messages, current_iter_start, keep_latest_reads=keep_latest_reads)

        payload = {
            "model": model_name,
            "messages": messages,
            "tools": tool_schemas,
            "tool_choice": "auto",
            "max_tokens": settings.generation_max_tokens,
        }
        if session_id:
            payload["session_id"] = session_id

        data = chat_completion(payload, timeout=settings.generation_call_timeout_seconds)

        usage = data.get("usage") or {}
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as exc:
            raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc

        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if message.get("content"):
            last_content = message["content"]

        trace_entry = {
            "iteration": iteration,
            "finish_reason": choice.get("finish_reason"),
            "assistant_content": message.get("content"),
            "cache_usage": usage.get("prompt_tokens_details"),
            "tool_calls": [],
        }

        if not tool_calls:
            if choice.get("finish_reason") == "length":
                # Cut off before producing a single tool call or any content --
                # NOT a legitimate "I'm done" signal, just an empty response
                # that happens to also have zero tool_calls. Treating this as
                # completion (the old behavior) let generation "succeed" with
                # no files ever written. Retry instead, same as the
                # truncated-mid-tool-call handling below.
                trace.append(trace_entry)
                _flush_trace()
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your last response was cut off before producing any "
                            "tool call or final message (hit the output token "
                            "limit with no progress). Start immediately with a "
                            "write_file call for the first page -- do not spend "
                            "the response on planning or reasoning text first."
                        ),
                    }
                )
                signature = "length:no_tool_calls"
                failure_counts[signature] = failure_counts.get(signature, 0) + 1
                if failure_counts[signature] >= settings.generation_max_consecutive_failures:
                    raise GenerationError(
                        f"Aborting after {failure_counts[signature]} responses cut off "
                        "before any tool call or content -- the model appears unable to "
                        "produce output within generation_max_tokens."
                    )
                continue

            missing_files = _missing_required_output_files(trace_path, required_files=required_files)
            if missing_files:
                # The model believes it's done (finish_reason != "length",
                # no more tool calls), but a required file from an earlier
                # failed write_file call was never actually retried -- seen
                # for real: one write_file in a multi-call iteration failed
                # (malformed tool-call JSON from the model), the other
                # succeeded, so the per-iteration failure tracking below
                # never triggered (that iteration still counted as a
                # success), and the model's own final summary confidently
                # described the missing file as created anyway. Treat a
                # missing required deliverable the same way a truncated
                # response is treated -- not a legitimate completion signal.
                trace.append(trace_entry)
                _flush_trace()
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You reported finishing, but these required files "
                            f"were never actually written: {', '.join(missing_files)}. "
                            "Call write_file now for each missing file -- do not "
                            "explain or apologize first."
                        ),
                    }
                )
                signature = f"premature_stop:missing:{','.join(missing_files)}"
                failure_counts[signature] = failure_counts.get(signature, 0) + 1
                if failure_counts[signature] >= settings.generation_max_consecutive_failures:
                    raise GenerationError(
                        f"Aborting: the model repeatedly claimed completion without "
                        f"actually writing required file(s) {', '.join(missing_files)}."
                    )
                continue

            trace.append(trace_entry)
            _flush_trace()
            return message.get("content") or "", total_usage, iteration

        iteration_had_success = False
        iteration_failure_signature: str | None = None

        for tool_call in tool_calls:
            fn = tool_call.get("function") or {}
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"

            if choice.get("finish_reason") == "length":
                result = (
                    "Error: your response was cut off before this tool call finished "
                    "(hit the output token limit) -- the call was not executed. Write "
                    "shorter file contents, or split this file's content across a "
                    "smaller first write_file call plus follow-up edits, then retry."
                )
                # Discard the truncated payload immediately (it can be a
                # multi-KB cut-off write_file) instead of letting it linger
                # in context and get resent on every later iteration.
                fn["arguments"] = json.dumps(
                    {"note": "discarded -- response truncated before this call finished"}
                )
                if iteration_failure_signature is None:
                    iteration_failure_signature = f"length:{name}"
            else:
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    result = (
                        f"Error: arguments for {name} were not valid JSON (got: "
                        f"{raw_args[:200]!r}) -- retry with well-formed, complete arguments."
                    )
                    args = None
                    fn["arguments"] = json.dumps(
                        {"note": "discarded -- malformed JSON, not executed"}
                    )
                    if iteration_failure_signature is None:
                        iteration_failure_signature = f"malformed_json:{name}"

                if args is not None:
                    handler = dispatch.get(name)
                    if handler is None:
                        result = f"Unknown tool: {name}"
                        if iteration_failure_signature is None:
                            iteration_failure_signature = f"unknown_tool:{name}"
                    else:
                        try:
                            result = handler(**args)
                            iteration_had_success = True
                        except GenerationError as exc:
                            result = f"Error: {exc}"
                            if iteration_failure_signature is None:
                                iteration_failure_signature = f"error:{name}"
                        except TypeError as exc:
                            result = f"Error: invalid arguments for {name}: {exc}"
                            if iteration_failure_signature is None:
                                iteration_failure_signature = f"bad_args:{name}"

            trace_entry["tool_calls"].append(
                {"name": name, "arguments": raw_args, "result": str(result)[:500]}
            )
            _emit(
                {
                    "type": "tool",
                    "iteration": iteration,
                    "tool": name,
                    "args": args if choice.get("finish_reason") != "length" and isinstance(args, dict) else {},
                    "ok": not str(result).startswith(("Error", "Unknown tool")),
                    "result": str(result)[:200],
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "content": str(result),
                }
            )

        trace.append(trace_entry)
        _flush_trace()

        if not iteration_had_success:
            signature = iteration_failure_signature or "unknown"
            failure_counts[signature] = failure_counts.get(signature, 0) + 1

            if failure_counts[signature] >= settings.generation_max_consecutive_failures:
                raise GenerationError(
                    f"Aborting after the same failure recurred {failure_counts[signature]} "
                    f"times ({signature}) -- the agent appears stuck and unlikely to "
                    "recover within the remaining iteration budget."
                )

    raise IterationLimitError(
        f"Agent did not finish within {max_iterations} iterations",
        usage=total_usage,
        iterations=max_iterations,
        last_content=last_content,
    )


def _copy_images(project_root: Path, output_dir: Path, assets: list[dict]) -> list[str]:
    images_out = output_dir / "images"
    images_out.mkdir(parents=True, exist_ok=True)
    copied = []
    for asset in assets:
        if asset.get("asset_type") not in ("image", "icon"):
            continue
        src = project_root / asset["storage_path"]
        if not src.exists():
            continue
        dest = images_out / src.name
        dest.write_bytes(src.read_bytes())
        copied.append(src.name)
    return copied


def _build_user_message(design_md: str, image_names: list[str]) -> str:
    image_list = "\n".join(f"- images/{name}" for name in image_names) or "(no images available)"
    return (
        "Here is the business content and brand blueprint to build the site from "
        "(YAML frontmatter + page content):\n\n"
        f"{design_md}\n\n"
        "Available image files already in the output directory's images/ folder "
        "(reference these exact paths, do not invent new ones):\n"
        f"{image_list}\n\n"
        "Build the complete website now."
    )
