"""Admin-managed design-strategy prompt templates. The prompt TEXT always
stays a plain .txt file on disk in backend/prompts/ (PROMPTS_DIR) -- this
module only tracks lightweight metadata (category/active-state/audit) in
the `prompt_templates` table, mirroring AIModelSetting's audit shape.

A file present on disk with no DB row is treated as active by default (see
get_active_template_filenames) -- this is what lets the pre-existing
hand-written templates keep working with no backfill migration, while an
admin can still explicitly disable one later (the first toggle is also the
first time that file gets a real row -- see set_active).

This repo has a documented history of path-traversal bugs in file-writing
code (see CLAUDE.md's blueprint-pipeline code-review-pass note and
generation_tools._resolve_safe_path), so every function here that touches
a filesystem path independently re-validates it against PROMPTS_DIR rather
than trusting a caller-supplied filename.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.site_generator import PROMPTS_DIR
from ..models import PromptTemplate

MAX_UPLOAD_BYTES = 200 * 1024  # hand-authored text prompts, not data files
MAX_NAME_LENGTH = 64
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def sanitize_template_name(raw: str) -> str:
    """Strips a trailing .txt, then requires the result to be a non-empty
    string of only letters/digits/-/_ -- rejects (never silently strips)
    anything else, including '..', '/', '\\', null bytes, and
    whitespace-only input. Applied to both the admin-chosen category and
    the template name, since both become filename components."""
    if raw is None:
        raise ValueError("name is required")
    name = raw.strip()
    if name.lower().endswith(".txt"):
        name = name[: -len(".txt")]
    if not name or len(name) > MAX_NAME_LENGTH or not _SAFE_NAME_RE.match(name):
        raise ValueError(f"{raw!r} is not a valid name (use only letters, digits, - and _)")
    return name


def build_filename(category: str, name: str) -> str:
    """Matches the existing {category}_{name}_prompt.txt convention. Both
    arguments must already be sanitized by sanitize_template_name."""
    return f"{category}_{name}_prompt.txt"


def _infer_category(filename: str) -> str:
    """Best-effort category for a legacy/untracked file -- everything
    before the first underscore, per the naming convention. Display only;
    never used to reconstruct a filesystem path."""
    return filename.split("_", 1)[0] if "_" in filename else filename


def _resolve_in_prompts_dir(filename: str) -> Path:
    prompts_root = PROMPTS_DIR.resolve()
    candidate = (PROMPTS_DIR / filename).resolve()
    if candidate != prompts_root and not candidate.is_relative_to(prompts_root):
        raise ValueError(f"resolved path escapes the prompts directory: {filename}")
    return candidate


def save_uploaded_template(
    db: Session,
    *,
    category: str,
    raw_name: str,
    content: bytes,
    admin_id: uuid.UUID,
) -> PromptTemplate:
    """Sanitizes category+name, builds the filename, verifies the resolved
    path stays inside PROMPTS_DIR, rejects an existing file (no silent
    overwrite), enforces a size cap and UTF-8 text content, writes the
    file, then inserts the metadata row. If the DB insert fails after the
    file write, the file is deleted so disk and DB never disagree."""
    safe_category = sanitize_template_name(category)
    safe_name = sanitize_template_name(raw_name)
    filename = build_filename(safe_category, safe_name)

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"template file too large ({len(content)} bytes, max {MAX_UPLOAD_BYTES})")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("template file must be valid UTF-8 text") from exc

    dest = _resolve_in_prompts_dir(filename)
    if dest.exists():
        raise FileExistsError(f"a template named {filename!r} already exists")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    try:
        row = PromptTemplate(
            filename=filename, category=safe_category, is_active=True, uploaded_by_admin_id=admin_id
        )
        db.add(row)
        db.flush()
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return row


@dataclass(frozen=True)
class TemplateViewRow:
    filename: str
    category: str
    is_active: bool
    uploaded_by_admin_id: uuid.UUID | None
    uploaded_at: datetime | None


def get_all_templates_for_admin_view(db: Session) -> list[TemplateViewRow]:
    """Merges DB rows with any PROMPTS_DIR/*.txt file that has no DB row
    yet, so the admin list shows every file on disk, not just ones an
    admin has explicitly uploaded or toggled."""
    tracked = {row.filename: row for row in db.scalars(select(PromptTemplate)).all()}
    on_disk = sorted(p.name for p in PROMPTS_DIR.glob("*.txt"))

    rows: list[TemplateViewRow] = []
    for filename in on_disk:
        tracked_row = tracked.get(filename)
        if tracked_row is not None:
            rows.append(
                TemplateViewRow(
                    filename=tracked_row.filename,
                    category=tracked_row.category,
                    is_active=tracked_row.is_active,
                    uploaded_by_admin_id=tracked_row.uploaded_by_admin_id,
                    uploaded_at=tracked_row.uploaded_at,
                )
            )
        else:
            rows.append(
                TemplateViewRow(
                    filename=filename,
                    category=_infer_category(filename),
                    is_active=True,
                    uploaded_by_admin_id=None,
                    uploaded_at=None,
                )
            )
    return rows


def set_active(db: Session, filename: str, is_active: bool, admin_id: uuid.UUID) -> PromptTemplate:
    """Upsert-by-filename -- this is the lazy backfill point where a
    legacy, previously-untracked file gets its first real row."""
    row = db.scalar(select(PromptTemplate).where(PromptTemplate.filename == filename))
    if row is None:
        if not (PROMPTS_DIR / filename).exists():
            raise ValueError(f"no such template file: {filename}")
        row = PromptTemplate(
            filename=filename,
            category=_infer_category(filename),
            is_active=is_active,
            uploaded_by_admin_id=admin_id,
        )
        db.add(row)
    else:
        row.is_active = is_active
    db.flush()
    return row


def delete_template(db: Session, filename: str) -> None:
    """Re-validates the path independently rather than trusting the
    caller-supplied filename -- removes the on-disk file (if present) and
    the DB row (if present)."""
    target = _resolve_in_prompts_dir(filename)
    if target.exists():
        target.unlink()
    row = db.scalar(select(PromptTemplate).where(PromptTemplate.filename == filename))
    if row is not None:
        db.delete(row)
        db.flush()


def get_active_template_filenames(db: Session) -> list[str]:
    """Used by tasks_generate.py before calling generate_site(). A file is
    a candidate if it's untracked (default-active) or tracked with
    is_active=True."""
    disabled = {
        row.filename
        for row in db.scalars(select(PromptTemplate).where(PromptTemplate.is_active.is_(False))).all()
    }
    return [p.name for p in PROMPTS_DIR.glob("*.txt") if p.name not in disabled]
