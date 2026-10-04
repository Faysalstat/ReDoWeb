import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.blueprint_pipeline import run_blueprint_pipeline
from ..ai.errors import BlueprintExtractionError, OpenRouterError
from ..config import get_settings
from ..db.session import get_db
from ..models import Blueprint, Project
from ..schemas.blueprint import BlueprintResponse
from ..services.blueprint_service import build_blueprint_row

router = APIRouter(prefix="/api/v1", tags=["blueprint"])


@router.post("/projects/{project_id}/blueprint", response_model=BlueprintResponse)
def create_blueprint(project_id: str, db: Session = Depends(get_db)) -> BlueprintResponse:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    if not project_root.exists():
        raise HTTPException(
            status_code=404, detail=f"No crawled project found for id {project_id}"
        )

    project = db.get(Project, uuid.UUID(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"No project record found for id {project_id}")

    try:
        result = run_blueprint_pipeline(project_root)
    except (BlueprintExtractionError, OpenRouterError) as exc:
        project.status = "failed"
        project.rejection_reason = str(exc)
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.query(Blueprint).filter(
        Blueprint.project_id == project.id, Blueprint.is_current.is_(True)
    ).update({"is_current": False})
    next_version = db.query(Blueprint).filter(Blueprint.project_id == project.id).count() + 1

    db.add(build_blueprint_row(project.id, next_version, result))
    project.status = "blueprint_ready"
    db.commit()

    return BlueprintResponse(project_id=project_id, version=next_version, **result)
