import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from ..auth.jwt import InvalidTokenError
from ..config import get_settings

PREVIEW_TOKEN_TTL = timedelta(minutes=5)
_PREVIEW_PURPOSE = "preview"


class PreviewPathError(Exception):
    """Raised when a requested preview file path escapes the project's
    storage directory (traversal attempt)."""


def build_preview_url_path(project_id: str, output_dir: str) -> str:
    """The one place a preview path is constructed -- replaces the duplicated
    f"/preview/{project_id}/{output_dir}/index.html" string that used to be
    built separately in routers/generation.py and workers/tasks_generate.py."""
    return f"/api/v1/preview/{project_id}/{output_dir}/index.html"


def mint_preview_token(project_id: str) -> str:
    """Short-lived, purpose-scoped token for iframing a generated site.
    Deliberately a distinct claim shape from the login JWT (auth/jwt.py) so
    the two can never be confused for one another."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "project_id": project_id,
        "purpose": _PREVIEW_PURPOSE,
        "iat": now,
        "exp": now + PREVIEW_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_preview_token(token: str, project_id: str) -> None:
    """Raises InvalidTokenError unless `token` is an unexpired preview token
    minted for exactly this project_id."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("purpose") != _PREVIEW_PURPOSE or payload.get("project_id") != project_id:
        raise InvalidTokenError("Token not valid for this project")


def resolve_safe_path(project_id: str, file_path: str) -> Path:
    """Resolves `file_path` against this project's storage directory,
    rejecting any attempt to escape it (path traversal via `..`, absolute
    paths, symlinks pointing outside)."""
    settings = get_settings()
    project_root = (Path(settings.storage_root) / "projects" / project_id).resolve()
    candidate = (project_root / file_path).resolve()
    if not candidate.is_relative_to(project_root):
        raise PreviewPathError("Path escapes project directory")
    return candidate


def guess_content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"
