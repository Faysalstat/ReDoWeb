import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..ai.errors import GenerationError
from ..ai.site_generator import generate_site
from ..config import get_settings
from ..db.session import SessionLocal
from ..models import Blueprint, GenerationJob, GenerationOutput, Project
from ..services import (
    model_config_service,
    prompt_template_service,
    tier_service,
    token_usage_service,
    wallet_service,
)
from ..services.preview_service import build_preview_url_path
from ..services.storage_capacity_service import InsufficientDiskSpaceError, check_free_disk_space
from ..services.wallet_service import InsufficientCreditsError


def generate_tier_task(project_id: str, tier: str) -> dict:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))

        # Defensive re-check -- submission already checked this, but other
        # concurrent projects may have consumed space since then (see
        # docs/concurrency-scaling-plan.md).
        try:
            check_free_disk_space()
        except InsufficientDiskSpaceError as exc:
            project.status = "failed"
            project.rejection_reason = str(exc)
            db.commit()
            raise

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
            project_id=project.id,
            blueprint_id=blueprint_row.id,
            tier=tier,
            overall_status="running",
            scope="preview",
        )
        db.add(job)
        project.status = "generating"
        db.commit()

        # Charged once per project regardless of how many tiers are enabled --
        # the idempotency_key is scoped to project_id only, so when multiple
        # tiers' generate_tier_task calls run concurrently (fan-out enqueue
        # in tasks_blueprint.py, multiple queue workers), only the first to
        # commit actually debits; the rest see the existing ledger row and
        # no-op. This relies on wallet_service.spend() locking the wallet row
        # *before* checking the idempotency key -- see its docstring. This
        # runs after crawl+blueprint have already succeeded, so a
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
            job.finished_at = datetime.now(timezone.utc)
            project.status = "failed"
            project.rejection_reason = "Insufficient credits"
            db.commit()
            raise

        try:
            generation_model = model_config_service.get_generation_model(tier, db)
            candidate_templates = prompt_template_service.get_active_template_filenames(db)
            result = generate_site(
                project_root,
                tier,
                generation_model=generation_model,
                candidate_templates=candidate_templates,
            )
        except Exception as exc:
            job.overall_status = "failed"
            job.failure_reason = str(exc)
            job.finished_at = datetime.now(timezone.utc)
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
                preview_url_path=build_preview_url_path(project_id, result["output_dir"]),
                summary=result["summary"],
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"],
                iterations=result["iterations"],
                contrast_warnings=postprocess["contrast_warnings"],
                alt_text_added=postprocess["alt_text_added"],
                og_tags_added=postprocess["og_tags_added"],
                reveal_visibility_fixes=postprocess["reveal_visibility_fixes"],
                sitemap_written=postprocess["sitemap_written"],
            )
        )
        token_usage_service.record_usage(
            db,
            project_id=project.id,
            user_id=project.user_id,
            job_id=job.id,
            model_name=result["model"],
            purpose="generation",
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=result["usage"]["completion_tokens"],
        )

        job.overall_status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)

        # All enabled tiers' generate_tier jobs are enqueued up front (see
        # tasks_blueprint.py) and may finish in any order, possibly
        # concurrently on different queue workers. Only flip the project to
        # the terminal "ready" status once every enabled tier has actually
        # succeeded -- recomputed by set membership rather than by chain
        # position, so this is correct regardless of which tier finishes
        # last. Otherwise the frontend's poll (which stops on any terminal
        # status) would stop after the first tier and never see the rest
        # complete.
        enabled_tier_keys = {enabled_tier.key for enabled_tier in tier_service.get_enabled_tiers(db)}
        succeeded_tier_keys = {
            row.tier
            for row in db.query(GenerationJob)
            .filter(GenerationJob.project_id == project.id, GenerationJob.overall_status == "succeeded")
            .all()
        }
        succeeded_tier_keys.add(tier)
        project.status = "ready" if enabled_tier_keys <= succeeded_tier_keys else "generating"

        db.commit()
        return result
    finally:
        db.close()
