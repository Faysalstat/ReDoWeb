import mimetypes
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from ..auth.jwt import InvalidTokenError
from ..config import get_settings

PREVIEW_TOKEN_TTL = timedelta(minutes=5)
_PREVIEW_PURPOSE = "preview"

# Matches href="..."/src="..." in HTML whose value is a same-directory
# relative reference (not absolute, not an anchor, not a data:/mailto:/tel:
# link) -- exactly the shape generated pages use for style.css, script.js,
# and images/... per site_generator.py's TECH_CONSTRAINTS.
_HTML_ASSET_ATTR_RE = re.compile(
    r'(?P<attr>href|src)="(?!https?://|//|/|#|data:|mailto:|tel:)(?P<url>[^"]+)"'
)
# Matches CSS url(...) references with the same relative-only scope.
_CSS_URL_RE = re.compile(
    r'url\(\s*(?P<quote>[\'"]?)(?!https?://|//|data:)(?P<url>[^\'")]+)(?P=quote)\s*\)'
)


def _append_token(url: str, token: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}preview_token={token}"


def rewrite_relative_asset_urls(text: str, token: str, is_css: bool) -> str:
    """The iframe's top-level HTML request carries `?preview_token=...`, but
    the browser resolves a page's own relative asset references (style.css,
    images/...) WITHOUT copying that query string over -- those sub-requests
    then hit /api/v1/preview/... with no token and 422 (a required query
    param), so the page renders unstyled with broken images. Rewriting every
    relative href/src (HTML) or url(...) (CSS) to carry the same token
    forward fixes this without weakening the token check itself."""
    if is_css:
        return _CSS_URL_RE.sub(
            lambda m: f"url({m.group('quote')}{_append_token(m.group('url'), token)}{m.group('quote')})",
            text,
        )
    return _HTML_ASSET_ATTR_RE.sub(
        lambda m: f'{m.group("attr")}="{_append_token(m.group("url"), token)}"', text
    )


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
