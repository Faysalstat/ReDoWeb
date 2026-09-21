import uuid
from pathlib import Path

from ..ai.blueprint_pipeline import run_blueprint_pipeline
from ..config import get_settings
from ..db.session import SessionLocal
from ..models import Blueprint, Project
from ..services import model_config_service, token_usage_service
from ..services.blueprint_service import build_blueprint_row
from .queue import enqueue


def extract_blueprint_task(project_id: str, tier_keys: list[str]) -> str:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))
        project.status = "extracting_blueprint"
        db.commit()

        vision_model = model_config_service.get_vision_model(db)
        try:
            # Initial pipeline run: AI-review only the home page (index 0)
            # regardless of how many pages were crawled -- keeps preview
            # AI-review cost matched to what site_generator.generate_site()
            # actually uses today. The rest of a multi-page crawl's pages
            # are reviewed later, lazily, only if/when a user pays to
            # download a full multi-page site (see tasks_full_site.py).
            result = run_blueprint_pipeline(
                project_root, vision_model=vision_model, page_indices=[0], include_meta=True
            )
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
            model_name=vision_model,
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

        # Fan out: every enabled tier's generate_tier job is enqueued here,
        # up front, instead of chaining one at a time. Multiple queue workers
        # (see docs/concurrency-scaling-plan.md) can then claim and run them
        # concurrently, and each tier now succeeds or fails independently --
        # previously, one tier raising meant every tier after it in the
        # chain silently never even attempted to run.
        for tier_key in tier_keys:
            enqueue(db, "generate_tier", {"project_id": project_id, "tier": tier_key})

        db.commit()
        return project_id
    finally:
        db.close()
