import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.errors import GenerationError
from ..ai.site_generator import generate_site
from ..config import get_settings
from ..db.session import get_db
from ..models import Blueprint, GenerationJob, GenerationOutput, Project
from ..schemas.generation import GenerationResponse
from ..services.preview_service import build_preview_url_path

router = APIRouter(prefix="/api/v1", tags=["generation"])


@router.post("/projects/{project_id}/generate", response_model=GenerationResponse)
def create_generation(project_id: str, tier: str = "pro", db: Session = Depends(get_db)) -> GenerationResponse:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    if not project_root.exists():
        raise HTTPException(
            status_code=404, detail=f"No crawled project found for id {project_id}"
        )

    project = db.get(Project, uuid.UUID(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"No project record found for id {project_id}")

    blueprint_row = (
        db.query(Blueprint)
        .filter(Blueprint.project_id == project.id, Blueprint.is_current.is_(True))
        .one_or_none()
    )
    if blueprint_row is None:
        raise HTTPException(
            status_code=422, detail="No blueprint found for this project -- run blueprint extraction first"
        )

    job = GenerationJob(
        project_id=project.id, blueprint_id=blueprint_row.id, tier=tier, overall_status="running"
    )
    db.add(job)
    project.status = "generating"
    db.commit()

    try:
        result = generate_site(project_root, tier)
    except GenerationError as exc:
        job.overall_status = "failed"
        job.failure_reason = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        project.status = "failed"
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    postprocess = result["postprocess"]
    db.add(
        GenerationOutput(
            job_id=job.id,
            template_used=result["template_used"],
            output_storage_path=result["output_dir"],
            preview_url_path=build_preview_url_path(project_id, result["output_dir"]),
            summary=result["summary"],
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=result["usage"]["completion_tokens"],
            iterations=result["iterations"],
            contrast_warnings=postprocess["contrast_warnings"],
            alt_text_added=postprocess["alt_text_added"],
            og_tags_added=postprocess["og_tags_added"],
            sitemap_written=postprocess["sitemap_written"],
        )
    )
    job.overall_status = "succeeded"
    job.finished_at = datetime.now(timezone.utc)
    project.status = "ready"
    db.commit()

    return GenerationResponse(project_id=project_id, **result)
