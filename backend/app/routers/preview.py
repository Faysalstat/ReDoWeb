import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.jwt import InvalidTokenError
from ..db.session import get_db
from ..models import Project, User
from ..schemas.preview import PreviewTokenResponse
from ..services.preview_service import (
    PREVIEW_TOKEN_TTL,
    PreviewPathError,
    guess_content_type,
    mint_preview_token,
    resolve_safe_path,
    verify_preview_token,
)

router = APIRouter(prefix="/api/v1", tags=["preview"])


@router.post("/projects/{project_id}/preview-token", response_model=PreviewTokenResponse)
def create_preview_token(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreviewTokenResponse:
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or (project.user_id != current_user.id and not current_user.is_admin):
        # Same 404 for "doesn't exist" and "not yours", matching
        # GET /projects/{id}'s existing no-leak convention -- this single
        # check covers both the regular owner-previews-their-own-project
        # flow and the new admin cross-user preview flow.
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")

    token = mint_preview_token(project_id)
    return PreviewTokenResponse(preview_token=token, expires_in=int(PREVIEW_TOKEN_TTL.total_seconds()))


@router.get("/preview/{project_id}/{file_path:path}")
def serve_preview_file(project_id: str, file_path: str, preview_token: str) -> FileResponse:
    # No bearer dependency here on purpose -- an <iframe src> can't carry an
    # Authorization header, so the short-lived token travels in the query
    # string instead (minted via the authenticated POST above).
    try:
        verify_preview_token(preview_token, project_id)
    except InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid or expired preview token")

    try:
        resolved_path = resolve_safe_path(project_id, file_path)
    except PreviewPathError:
        raise HTTPException(status_code=403, detail="Invalid path")

    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Preview file not found")

    return FileResponse(resolved_path, media_type=guess_content_type(resolved_path))
