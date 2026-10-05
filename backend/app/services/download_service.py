import fnmatch
import os
import uuid
import zipfile
from pathlib import Path

from ..config import get_settings

# Internal artifacts that live in the generated output folder but aren't
# part of the user's site: the agent loop's per-iteration debug traces and
# the structured blueprint (design.md is the user-facing blueprint and IS
# shipped, per PRD FR9). Matched against each file's name, at any depth.
EXCLUDED_NAME_PATTERNS = ("_debug_trace*.json", "blueprint.json")


def is_excluded(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_NAME_PATTERNS)


def write_site_zip(output_dir: Path, archive_path: Path) -> Path:
    """Zips `output_dir` into `archive_path`, skipping internal artifacts.
    Written to a temp file then atomically renamed, so two concurrent
    downloads of the same tier never serve a half-written archive."""
    tmp_path = archive_path.with_name(f".{archive_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output_dir.rglob("*")):
                if path.is_file() and not is_excluded(path.name):
                    archive.write(path, path.relative_to(output_dir).as_posix())
        os.replace(tmp_path, archive_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return archive_path


def build_download_zip(project_id: str, tier_key: str, output_storage_path: str) -> Path:
    """Zips the generated output folder for one tier into
    {storage_root}/projects/{project_id}/downloads/{tier_key}.zip, rebuilt on
    every call -- output is overwritten in place on every generate_tier_task
    run (see site_generator.generate_site), so a stale zip would silently
    serve old content otherwise."""
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    output_dir = project_root / output_storage_path
    downloads_dir = project_root / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return write_site_zip(output_dir, downloads_dir / f"{tier_key}.zip")
