"""Sandboxed file tools for the landing-page agent.

The agent (driven via OpenRouter's OpenAI-compatible tool calling) gets
write_file/read_file/list_files scoped to one run's output directory. Every
path the model supplies is untrusted input -- resolved to its canonical
form and checked against the sandbox root before any filesystem operation.
"""

from pathlib import Path

from .errors import GenerationError

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write a file inside the output directory, creating parent "
                "directories as needed. Overwrites if the file already exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": 'Relative path within the output directory, e.g. "index.html", "styles.css", or "script.js".',
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


def make_tool_dispatch(sandbox_root: Path) -> dict:
    sandbox_root = sandbox_root.resolve()

    def write_file(path: str, content: str) -> str:
        target = _resolve_safe_path(sandbox_root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
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
