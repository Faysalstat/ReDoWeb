"""Sandboxed file tools for the site-generation agent.

The agent (driven via OpenRouter's OpenAI-compatible tool calling) gets
write_file/read_file/list_files scoped to one project's generated-output
directory. Every path the model supplies is untrusted input -- resolved to
its canonical form and checked against the sandbox root before any
filesystem operation, per the path-traversal guidance in the Claude API
skill's Client-Side Tools section (the same principle applies regardless
of which model/provider is calling the tool).
"""

import re
from pathlib import Path

from .errors import GenerationError

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write a file inside the site output directory, creating parent "
                "directories as needed. Overwrites if the file already exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": 'Relative path within the output directory, e.g. "index.html", "style.css", or "about.html".',
                    },
                    "content": {
                        "type": "string",
                        "description": "Full text content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read back a file previously written in the output directory, "
                "to check or revise your own work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path within the output directory.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files already present in the output directory (or a "
                "subdirectory), including the pre-populated images/ folder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Relative subdirectory to list; defaults to the output root.",
                    },
                },
                "required": [],
            },
        },
    },
]


EDIT_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Replace one exact snippet of an existing file with new text. "
            "old_string must appear exactly once in the file (include enough "
            "surrounding text to make it unique). Use this for every change to "
            "an existing page -- never rewrite a whole file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'Relative path within the output directory, e.g. "index.html".',
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact existing text to replace (must match exactly once).",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement text.",
                },
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
}

# The SEO pass (seo_agent.py) gets edit_file instead of whole-file rewrites,
# plus the read-only tools -- write_file stays available only for creating
# brand-new files (see make_seo_tool_dispatch).
SEO_TOOL_SCHEMAS = [TOOL_SCHEMAS[0], EDIT_FILE_SCHEMA, TOOL_SCHEMAS[1], TOOL_SCHEMAS[2]]

# Existing files with these extensions are the delivered design -- the SEO
# pass may only edit them in place, never replace them wholesale.
_SEO_PROTECTED_SUFFIXES = (".html", ".htm", ".css", ".js")


def _resolve_safe_path(sandbox_root: Path, relative_path: str) -> Path:
    sandbox_resolved = sandbox_root.resolve()
    # Models routinely say "/" or "/index.html" meaning the site root (seen
    # in a real SEO run: list_files("/") -> "escapes sandbox"). A leading
    # slash is treated as sandbox-relative; the containment check below
    # still rejects anything that resolves outside the sandbox.
    cleaned = (relative_path or ".").lstrip("/\\") or "."
    candidate = (sandbox_resolved / cleaned).resolve()
    if candidate != sandbox_resolved and not candidate.is_relative_to(sandbox_resolved):
        raise GenerationError(f"Path escapes output sandbox: {relative_path}")
    return candidate


def _normalized_rel_path(sandbox_root: Path, relative_path: str) -> str:
    """Canonical sandbox-relative posix path ("./index.html", "/index.html"
    and "index.html" all -> "index.html"), so locked/append-only checks
    can't be sidestepped by spelling the same file differently."""
    target = _resolve_safe_path(sandbox_root, relative_path)
    return target.relative_to(sandbox_root.resolve()).as_posix()


_ENTITY_EQUIVALENTS = {"&": r"(?:&amp;|&#0*38;|&)", '"': r"(?:\"|'|&quot;)", "'": r"(?:'|\"|&#0*39;|&#x27;)"}


def _tolerant_pattern(old_string: str) -> re.Pattern | None:
    """A regex for old_string that tolerates the ways a model's snippet
    differs from BeautifulSoup-serialized HTML while meaning the same
    markup: `&` vs `&amp;`, " vs ', any whitespace run vs another, and
    `>` vs ` />`. Never tolerant about anything else (text, tag names,
    attribute values), so it can't match a different snippet."""
    text = old_string.replace("&amp;", "&").replace("&quot;", '"')
    parts: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            while i < len(text) and text[i].isspace():
                i += 1
            parts.append(r"\s+")
            continue
        if ch == "/" and text[i + 1 : i + 2] == ">":
            parts.append(r"\s*/?>")
            i += 2
            continue
        if ch == ">":
            parts.append(r"\s*/?>")
        else:
            parts.append(_ENTITY_EQUIVALENTS.get(ch, re.escape(ch)))
        i += 1
    try:
        return re.compile("".join(parts))
    except re.error:
        return None


def _escape_bare_ampersands(text: str) -> str:
    return re.sub(r"&(?!#?\w+;)", "&amp;", text)


def make_tool_dispatch(
    sandbox_root: Path,
    locked_files: set[str] | None = None,
    append_only_files: set[str] | None = None,
) -> dict:
    """`locked_files`/`append_only_files` are relative paths (matching the
    `path` argument write_file is called with, e.g. "index.html") given
    code-enforced protection during a full-site generation run
    (site_generator.generate_full_site()) so the already-generated,
    already-shown home page can't be silently clobbered by the model --
    this backs up FULL_SITE_TECH_CONSTRAINTS' prompt wording with an actual
    guarantee, the same "code-enforced, not prompt-trusted" pattern used
    throughout blueprint_review.py's merge functions. Both default to None
    (no restriction), so generate_site()'s existing call site is
    unaffected."""
    sandbox_root = sandbox_root.resolve()
    locked_files = locked_files or set()
    append_only_files = append_only_files or set()

    def write_file(path: str, content: str) -> str:
        rel = _normalized_rel_path(sandbox_root, path)
        if rel in locked_files:
            return (
                f"Error: {path} is the finished, already-shown design and cannot be "
                "rewritten -- build the other pages instead."
            )
        target = _resolve_safe_path(sandbox_root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if rel in append_only_files and target.exists():
            existing = target.read_text(encoding="utf-8")
            target.write_text(existing.rstrip("\n") + "\n\n" + content, encoding="utf-8")
            return f"Appended {len(content)} characters to the end of {path} (existing content preserved)"
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}"

    def read_file(path: str) -> str:
        target = _resolve_safe_path(sandbox_root, path)
        if not target.exists() or not target.is_file():
            return f"No such file: {path}"
        return target.read_text(encoding="utf-8")

    def list_files(directory: str = ".") -> str:
        target = _resolve_safe_path(sandbox_root, directory)
        if not target.exists():
            return "(directory does not exist)"
        entries = sorted(
            p.relative_to(sandbox_root).as_posix() for p in target.rglob("*") if p.is_file()
        )
        return "\n".join(entries) if entries else "(empty)"

    return {"write_file": write_file, "read_file": read_file, "list_files": list_files}


def make_seo_tool_dispatch(sandbox_root: Path, locked_files: set[str] | None = None) -> dict:
    """Tool dispatch for the post-purchase SEO pass (seo_agent.py). The
    site is already finished and paid for, so this is deliberately narrower
    than make_tool_dispatch: existing .html/.css/.js files can only be
    changed through edit_file (an exact, unique snippet replacement), never
    rewritten wholesale -- code-enforced so the SEO agent can't silently
    redesign or truncate a delivered page. write_file only ever creates new
    files. `locked_files` can't be touched at all."""
    base = make_tool_dispatch(sandbox_root)
    sandbox_root = sandbox_root.resolve()
    locked_files = locked_files or set()

    def write_file(path: str, content: str) -> str:
        if _normalized_rel_path(sandbox_root, path) in locked_files:
            return f"Error: {path} is locked and cannot be changed."
        target = _resolve_safe_path(sandbox_root, path)
        if target.exists():
            if target.suffix.lower() in _SEO_PROTECTED_SUFFIXES:
                return (
                    f"Error: {path} already exists and cannot be rewritten -- use edit_file "
                    "to change a specific snippet instead."
                )
            return f"Error: {path} already exists -- write_file only creates new files here."
        return base["write_file"](path, content)

    def edit_file(path: str, old_string: str, new_string: str) -> str:
        if _normalized_rel_path(sandbox_root, path) in locked_files:
            return f"Error: {path} is locked and cannot be changed."
        target = _resolve_safe_path(sandbox_root, path)
        if not target.exists() or not target.is_file():
            return f"Error: no such file: {path}"
        if not old_string:
            return "Error: old_string must not be empty."
        text = target.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 1:
            target.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
            return f"Edited {path}"
        if count > 1:
            return (
                f"Error: old_string appears {count} times in {path} -- include more "
                "surrounding text so it matches exactly once."
            )
        # No exact match: retry tolerating serialization-only differences
        # (&amp;, quote style, whitespace, />) -- see _tolerant_pattern.
        pattern = _tolerant_pattern(old_string)
        matches = list(pattern.finditer(text)) if pattern is not None else []
        if len(matches) == 1:
            match = matches[0]
            replacement = new_string
            if "&amp;" in match.group(0):
                replacement = _escape_bare_ampersands(replacement)
            target.write_text(text[: match.start()] + replacement + text[match.end() :], encoding="utf-8")
            return f"Edited {path}"
        if len(matches) > 1:
            return (
                f"Error: old_string matches {len(matches)} places in {path} -- include more "
                "surrounding text so it matches exactly once."
            )
        return (
            f"Error: old_string was not found in {path}. Prefer the structured tools "
            "(set_title, set_meta_description, set_image_alt, update_link, ...) -- they don't "
            "need exact text. If you must use edit_file, copy the snippet from a fresh read_file."
        )

    return {
        "write_file": write_file,
        "edit_file": edit_file,
        "read_file": base["read_file"],
        "list_files": base["list_files"],
    }
