"""Sandboxed file tools for the site-generation agent.

The agent (driven via OpenRouter's OpenAI-compatible tool calling) gets
write_file/read_file/list_files scoped to one project's generated-output
directory. Every path the model supplies is untrusted input -- resolved to
its canonical form and checked against the sandbox root before any
filesystem operation, per the path-traversal guidance in the Claude API
skill's Client-Side Tools section (the same principle applies regardless
of which model/provider is calling the tool).
"""

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


def _resolve_safe_path(sandbox_root: Path, relative_path: str) -> Path:
    sandbox_resolved = sandbox_root.resolve()
    candidate = (sandbox_root / relative_path).resolve()
    if candidate != sandbox_resolved and not candidate.is_relative_to(sandbox_resolved):
        raise GenerationError(f"Path escapes output sandbox: {relative_path}")
    return candidate


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
        if path in locked_files:
            return (
                f"Error: {path} is the finished, already-shown design and cannot be "
                "rewritten -- build the other pages instead."
            )
        target = _resolve_safe_path(sandbox_root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path in append_only_files and target.exists():
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
