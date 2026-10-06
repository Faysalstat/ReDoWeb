"""Post-purchase agentic SEO pass for Pro/Premium tiers -- see
docs/seo-agent-and-buy-flow-plan.md.

audit (code) -> agent (AI, constrained edit tools) -> finalize (code).

The agent only handles items that need judgment (titles, meta
descriptions, heading tags, alt text, JSON-LD, internal links, broken
links). Everything mechanical -- and every safety check on what the agent
wrote -- is done by seo_postprocess.finalize_seo afterwards, so nothing
here relies on the model following instructions voluntarily. It runs on the
generated/{tier}/seo/ copy only (see workers/tasks_seo.py).
"""

import json
import re
from pathlib import Path
from typing import Protocol

from ..config import get_settings
from .blueprint_legacy_compat import render_design_md_compat
from .blueprint_schema import BlueprintDocument
from .errors import IterationLimitError
from .seo_tools import ALL_SEO_TOOL_SCHEMAS, build_page_outline, make_structured_seo_dispatch
from .postprocess import page_url, site_origin_from_url  # noqa: F401 -- re-exported for callers
from .seo_postprocess import audit_seo, finalize_seo, html_pages
from .site_generator import PROMPTS_DIR, _run_agent_loop

# Hardcoded on purpose (user decision 2026-10-05) -- the backend is the only
# place this list lives; the frontend reads `seo_available` from the
# project status response instead of keeping its own copy.
SEO_TIER_KEYS = frozenset({"pro", "premium"})

SEO_PROMPT_PATH = PROMPTS_DIR / "seo" / "seo_agent_prompt.md"
SEO_TRACE_FILENAME = "_debug_trace_seo.json"

_HEADING_RE = re.compile(r"^h[1-6]$")

# The SEO job's steps, as [start, end) shares of the overall progress bar.
# Shared with workers/tasks_seo.py (which owns "prepare" and "save").
SEO_STEPS = (
    ("prepare", "Copying your site", 0, 5),
    ("audit", "Checking every page", 5, 12),
    ("agent", "Optimizing titles, descriptions, headings and links", 12, 85),
    ("checks", "Running safety checks", 85, 88),
    ("finalize", "Adding sitemap, robots.txt, structured data and image optimizations", 88, 97),
    ("save", "Saving", 97, 100),
)


class ProgressSink(Protocol):
    """What run_seo_pass needs from services/job_progress.JobProgress --
    a Protocol so this module stays free of DB imports."""

    def start_step(self, key: str, detail: str = "") -> None: ...
    def advance(self, fraction: float, detail: str | None = None) -> None: ...
    def log(self, message: str, level: str = "info") -> None: ...


class _NoProgress:
    def start_step(self, key: str, detail: str = "") -> None:
        pass

    def advance(self, fraction: float, detail: str | None = None) -> None:
        pass

    def log(self, message: str, level: str = "info") -> None:
        pass


# What an edit_file call changed, judged from the replacement text -- for a
# readable activity line ("Edited about.html: meta description"). Checked in
# order; the first match wins.
_EDIT_KINDS = (
    ("application/ld+json", "structured data"),
    ('name="description"', "meta description"),
    ("<title", "page title"),
    ("alt=", "image alt text"),
    ("<h1", "headings"),
    ("<h2", "headings"),
    ("<h3", "headings"),
    ("href=", "links"),
)


# Activity labels for the structured, parser-backed tools (seo_tools.py).
_STRUCTURED_EDIT_LABELS = {
    "set_title": "page title",
    "set_meta_description": "meta description",
    "set_image_alt": "image alt text",
    "set_heading_level": "headings",
    "update_link": "links",
    "link_phrase": "internal link",
    "add_structured_data": "structured data",
}


def describe_edit(args: dict) -> str:
    new = str(args.get("new_string", "")).lower()
    for marker, label in _EDIT_KINDS:
        if marker in new:
            return label
    return "content"


class _AgentActivity:
    """Turns _run_agent_loop's on_event stream into progress + activity
    log entries. Progress inside the agent step is the larger of
    "iterations used" and "pages touched", so the bar moves steadily either
    way without ever claiming the step is finished early."""

    def __init__(self, progress: ProgressSink, page_names: list[str]):
        self.progress = progress
        self.page_names = set(page_names)
        self.pages_touched: set[str] = set()
        self.iteration = 0
        self.max_iterations = 1
        self.edits = 0
        self.failed_edits = 0

    def _fraction(self) -> float:
        by_iterations = self.iteration / max(self.max_iterations, 1)
        by_pages = len(self.pages_touched) / max(len(self.page_names), 1)
        return min(max(by_iterations, by_pages * 0.9), 0.95)

    def __call__(self, event: dict) -> None:
        if event.get("type") == "iteration":
            self.iteration = event.get("iteration", self.iteration)
            self.max_iterations = event.get("max_iterations", self.max_iterations)
            self.progress.advance(self._fraction())
            return
        if event.get("type") != "tool":
            return
        tool = event.get("tool")
        args = event.get("args") or {}
        path = str(args.get("path") or args.get("directory") or "").lstrip("./")
        if path not in self.page_names and Path(path).name in self.page_names:
            path = Path(path).name  # e.g. "public/index.html" -> mapped to index.html by the tools
        if tool in ("read_file", "get_page_outline"):
            self.progress.advance(self._fraction(), f"Reviewing {path}")
            return
        if tool == "list_files":
            return
        what = _STRUCTURED_EDIT_LABELS.get(tool)
        if tool == "edit_file":
            what = describe_edit(args)
        elif tool == "write_file":
            what = "new file"
        if what is None:
            return
        if event.get("ok"):
            self.edits += 1
            if path in self.page_names:
                self.pages_touched.add(path)
            message = f"Created {path}" if tool == "write_file" else f"Edited {path}: {what}"
            self.progress.log(message)
            self.progress.advance(self._fraction(), message)
        else:
            self.failed_edits += 1
            self.progress.log(
                f"{tool} on {path or 'a file'} didn't apply: {event.get('result', '')[:160]}", "debug"
            )


def _heading_sequence(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    return [tag.name for tag in BeautifulSoup(html, "lxml").find_all(_HEADING_RE)]


def seo_iteration_budget(page_count: int) -> int:
    """Step budget for the SEO agent, scaled to the site (the shared
    24-step generation budget ran out on a real multi-page run)."""
    settings = get_settings()
    return min(
        settings.seo_max_iterations_cap,
        settings.seo_max_iterations_base + settings.seo_max_iterations_per_page * max(page_count, 1),
    )


def _outline_text_chars(page_count: int) -> int:
    # Keep the first message bounded on big sites: shorter excerpts per page.
    return 600 if page_count <= 5 else 300


def _build_user_message(
    blueprint: BlueprintDocument,
    site_origin: str,
    audit: dict,
    outlines: dict[str, dict] | None = None,
    max_iterations: int | None = None,
) -> str:
    outlines = outlines or {}
    page_lines = []
    for name, page_audit in audit["pages"].items():
        issues = audit["issues"].get(name) or ["no problems found by the automatic audit -- still check alt text and internal links"]
        block = (
            f"### {name}  ->  {page_url(site_origin, name)}\n"
            f"heading_retag_safe: {str(page_audit['heading_retag_safe']).lower()}\n"
            "problems:\n" + "\n".join(f"- {issue}" for issue in issues)
        )
        if name in outlines:
            block += "\noutline (indexes for the structured tools):\n" + json.dumps(outlines[name], ensure_ascii=False)
        page_lines.append(block)
    duplicates = []
    if audit["duplicate_titles"]:
        duplicates.append(f"Duplicate titles across pages: {json.dumps(audit['duplicate_titles'])}")
    if audit["duplicate_descriptions"]:
        duplicates.append(f"Duplicate meta descriptions across pages: {json.dumps(audit['duplicate_descriptions'])}")
    file_list = ", ".join(f'"{name}"' for name in audit["pages"])
    budget_line = (
        f"You have at most {max_iterations} steps (model responses) in total -- put several tool calls in "
        "each response (e.g. every change for one page at once) so every page gets done.\n"
        if max_iterations
        else ""
    )
    return (
        f"Site: {blueprint.meta.site_name}\n"
        f"Public address: {site_origin}\n\n"
        "## Where the files are\n"
        f"Every page is a file at the TOP LEVEL of your workspace: {file_list}. Use exactly these names as "
        'the `path` (e.g. "index.html") -- there is no public/, src/, dist/ or any other folder for pages. '
        "Images are under images/.\n"
        f"{budget_line}"
        "The outline of every page is already included below, so you can start editing straight away -- "
        "only call get_page_outline again for fresh indexes after changing a page's headings.\n\n"
        "## Pages (file -> public URL), what the automatic audit found, and each page's outline\n\n"
        + "\n\n".join(page_lines)
        + ("\n\n" + "\n".join(duplicates) if duplicates else "")
        + "\n\n## Business blueprint (the ONLY source of facts you may use)\n\n"
        + render_design_md_compat(blueprint)
        + "\n\nFix every page now."
    )


def _restore_unsafe_heading_changes(output_dir: Path, before: dict[str, str], audit: dict) -> list[str]:
    """Code backstop for the prompt's heading rule: if the agent retagged
    headings on a page whose CSS styles headings by tag (heading_retag_safe
    false), that page is restored to its pre-agent state -- a visual change
    to a paid-for design is worse than losing that page's SEO edits (the
    finalizer still applies the mechanical fixes to it)."""
    restored = []
    for name, html in before.items():
        if audit["pages"].get(name, {}).get("heading_retag_safe", True):
            continue
        path = output_dir / name
        if not path.exists():
            continue
        current = path.read_text(encoding="utf-8")
        if _heading_sequence(current) != _heading_sequence(html):
            path.write_text(html, encoding="utf-8")
            restored.append(name)
    return restored


def run_seo_pass(
    output_dir: Path,
    *,
    blueprint: BlueprintDocument,
    site_origin: str,
    generation_model: str | None = None,
    progress: ProgressSink | None = None,
) -> dict:
    """Runs audit -> agent -> finalize on `output_dir` in place. Raises
    (OpenRouterError/GenerationError) if the agent loop itself fails -- the
    caller (tasks_seo) marks the job failed and the user can retry; the
    previous output stays downloadable since this only ever runs on the
    seo/ copy."""
    settings = get_settings()
    generation_model = generation_model or settings.generation_model
    progress = progress or _NoProgress()

    progress.start_step("audit")
    audit_before = audit_seo(output_dir)
    pages_before = {p.name: p.read_text(encoding="utf-8") for p in html_pages(output_dir)}
    issue_count = sum(len(issues) for issues in audit_before["issues"].values())
    progress.log(f"Found {issue_count} issue(s) across {len(pages_before)} page(s)")
    for name, issues in audit_before["issues"].items():
        if issues:
            progress.log(f"{name}: {'; '.join(issues)}", "debug")

    max_iterations = seo_iteration_budget(len(pages_before))
    progress.start_step("agent", f"Working through {len(pages_before)} page(s)")
    system_prompt = SEO_PROMPT_PATH.read_text(encoding="utf-8")
    retag_unsafe = {name for name, page in audit_before["pages"].items() if not page["heading_retag_safe"]}
    text_chars = _outline_text_chars(len(pages_before))
    outlines = {name: build_page_outline(output_dir, name, retag_unsafe, text_chars) for name in pages_before}
    user_message = _build_user_message(blueprint, site_origin, audit_before, outlines, max_iterations)
    dispatch = make_structured_seo_dispatch(output_dir, retag_unsafe_pages=retag_unsafe)
    activity = _AgentActivity(progress, list(pages_before))
    progress.log(f"Step budget: {max_iterations} for {len(pages_before)} page(s)", "debug")

    stopped_early = False
    try:
        summary, usage, iterations = _run_agent_loop(
            settings,
            generation_model,
            system_prompt,
            user_message,
            dispatch,
            trace_path=output_dir / SEO_TRACE_FILENAME,
            required_files=(),
            tool_schemas=ALL_SEO_TOOL_SCHEMAS,
            on_event=activity,
            keep_latest_reads=True,
            max_iterations=max_iterations,
        )
    except IterationLimitError as exc:
        # Every edit so far is already on disk and valid (each tool call
        # applies a complete, checked change), so running out of steps
        # isn't a reason to throw them away -- finish the mechanical work
        # and report what wasn't reached. With no edits at all there's
        # nothing worth keeping: fail so the user can retry.
        if activity.edits == 0:
            raise
        stopped_early = True
        summary, usage, iterations = exc.last_content, exc.usage, exc.iterations
        missed = sorted(set(pages_before) - activity.pages_touched)
        progress.log(
            f"AI pass hit its {max_iterations}-step limit; keeping the {activity.edits} edit(s) it made"
            + (f" -- not reached: {', '.join(missed)}" if missed else ""),
            "warning",
        )
    progress.log(
        f"AI pass finished: {activity.edits} edit(s) on {len(activity.pages_touched)} page(s) "
        f"in {iterations} step(s)"
        + (f", {activity.failed_edits} edit(s) retried" if activity.failed_edits else "")
    )
    if activity.failed_edits and activity.failed_edits >= max(activity.edits, 1):
        # More failed edits than successful ones means the run struggled --
        # worth an operator look (full errors are in the debug entries and
        # the _debug_trace_seo.json trace).
        progress.log(
            f"{activity.failed_edits} edit attempt(s) failed vs {activity.edits} applied", "warning"
        )

    progress.start_step("checks")
    restored = _restore_unsafe_heading_changes(output_dir, pages_before, audit_before)
    for name in restored:
        progress.log(
            f"{name}: heading changes undone -- this page's design styles headings by tag", "warning"
        )

    progress.start_step("finalize")
    finalize_report = finalize_seo(output_dir, blueprint, site_origin)
    for line in _finalize_summary(finalize_report):
        progress.log(line)
    remaining = sum(len(issues) for issues in finalize_report["remaining_issues"].values())
    if remaining:
        progress.log(f"{remaining} issue(s) left for review (see the report)", "warning")

    report = {
        "site_origin": site_origin,
        "issues_before": {name: issues for name, issues in audit_before["issues"].items() if issues},
        "agent_summary": summary,
        "pages_restored_heading_changes": restored,
        **finalize_report,
    }
    report["edits"] = activity.edits
    report["pages_edited"] = sorted(activity.pages_touched)
    report["agent_stopped_early"] = stopped_early
    report["max_iterations"] = max_iterations
    return {
        "report": report,
        "usage": usage,
        "iterations": iterations,
        "model": generation_model,
        "summary": summary,
    }


def _finalize_summary(report: dict) -> list[str]:
    """Readable one-liners for what the deterministic finalizer did."""
    lines = []
    if report.get("images_optimized"):
        lines.append(f"Optimized {len(report['images_optimized'])} image(s)")
    if report.get("noindex_removed"):
        lines.append(f"Removed noindex from {', '.join(report['noindex_removed'])}")
    if report.get("https_rewritten"):
        lines.append(f"Switched {len(report['https_rewritten'])} link(s) to https")
    if report.get("jsonld_fields_removed"):
        lines.append(
            f"Removed {len(report['jsonld_fields_removed'])} structured-data claim(s) not backed by your site"
        )
    if report.get("jsonld_dropped_invalid"):
        lines.append(f"Dropped invalid structured data on {', '.join(report['jsonld_dropped_invalid'])}")
    if report.get("scripts_deferred"):
        lines.append(f"Deferred {len(report['scripts_deferred'])} script(s) for faster loading")
    lines.append("Wrote " + ", ".join(report.get("files_written", [])))
    return lines
