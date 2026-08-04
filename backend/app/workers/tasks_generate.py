import uuid
from pathlib import Path

from ..ai.errors import GenerationError
from ..ai.site_generator import generate_site
from ..config import get_settings
from ..db.session import SessionLocal
from ..models import Blueprint, GenerationJob, GenerationOutput, Project
from ..services import token_usage_service, wallet_service
from ..services.wallet_service import InsufficientCreditsError
from .celery_app import celery_app


@celery_app.task(bind=True)
def generate_tier_task(self, project_id: str, tier: str) -> dict:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))

        blueprint_row = (
            db.query(Blueprint)
            .filter(Blueprint.project_id == project.id, Blueprint.is_current.is_(True))
            .one_or_none()
        )
        if blueprint_row is None:
            project.status = "failed"
            project.rejection_reason = "No blueprint found for this project"
            db.commit()
            raise GenerationError("No blueprint found for this project")

        job = GenerationJob(
            project_id=project.id, blueprint_id=blueprint_row.id, tier=tier, overall_status="running"
        )
        db.add(job)
        project.status = "generating"
        db.commit()

        # Charged once per project regardless of how many tiers are enabled --
        # the idempotency_key is scoped to project_id only, so a second
        # generate_tier_task for the same project (a future multi-tier
        # parallel group) sees the existing ledger row and is a no-op here.
        # This runs after crawl+blueprint have already succeeded, so a
        # rejected/failed project never reaches this line -- no charge on
        # reject, per docs/implementation-plan.md's Milestone 4 note.
        try:
            wallet_service.spend(
                db,
                user_id=project.user_id,
                amount=wallet_service.GENERATION_SPEND_CREDITS,
                reason="generation_spend",
                related_project_id=project.id,
                related_job_id=job.id,
                idempotency_key=f"generation_spend:{project_id}",
            )
            db.commit()
        except InsufficientCreditsError as exc:
            job.overall_status = "failed"
            job.failure_reason = str(exc)
            project.status = "failed"
            project.rejection_reason = "Insufficient credits"
            db.commit()
            raise

        try:
            result = generate_site(project_root, tier)
        except Exception as exc:
            job.overall_status = "failed"
            job.failure_reason = str(exc)
            project.status = "failed"
            project.rejection_reason = str(exc)
            db.commit()
            raise

        postprocess = result["postprocess"]
        db.add(
            GenerationOutput(
                job_id=job.id,
                template_used=result["template_used"],
                output_storage_path=result["output_dir"],
                preview_url_path=f"/preview/{project_id}/{result['output_dir']}/index.html",
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
        token_usage_service.record_usage(
            db,
            project_id=project.id,
            user_id=project.user_id,
            job_id=job.id,
            model_name=settings.generation_model,
            purpose="generation",
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=result["usage"]["completion_tokens"],
        )

        job.overall_status = "succeeded"
        project.status = "ready"
        db.commit()
        return result
    finally:
        db.close()
