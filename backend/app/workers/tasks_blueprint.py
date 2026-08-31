import uuid
from pathlib import Path

from ..ai.blueprint_pipeline import run_blueprint_pipeline
from ..config import get_settings
from ..db.session import SessionLocal
from ..models import Blueprint, Project
from ..services import token_usage_service
from ..services.blueprint_service import build_blueprint_row
from .celery_app import celery_app


@celery_app.task(bind=True)
def extract_blueprint_task(self, project_id: str) -> str:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))
        project.status = "extracting_blueprint"
        db.commit()

        try:
            result = run_blueprint_pipeline(project_root)
        except Exception as exc:
            project.status = "failed"
            project.rejection_reason = str(exc)
            db.commit()
            raise

        token_usage_service.record_usage(
            db,
            project_id=project.id,
            user_id=project.user_id,
            job_id=None,
            model_name=settings.vision_model,
            purpose="blueprint_extraction",
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=result["usage"]["completion_tokens"],
        )

        db.query(Blueprint).filter(
            Blueprint.project_id == project.id, Blueprint.is_current.is_(True)
        ).update({"is_current": False})
        next_version = db.query(Blueprint).filter(Blueprint.project_id == project.id).count() + 1

        db.add(build_blueprint_row(project.id, next_version, result))
        project.status = "blueprint_ready"
        db.commit()
        return project_id
    finally:
        db.close()
