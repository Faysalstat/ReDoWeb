import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..ai.errors import GenerationError
from ..ai.site_generator import generate_site
from ..config import get_settings
from ..db.session import SessionLocal
from ..errors import user_facing_message
from ..models import Blueprint, GenerationJob, GenerationOutput, Project
from ..services import (
    generation_status_service,
    model_config_service,
    prompt_template_service,
    tier_service,
    token_usage_service,
    wallet_service,
)
from ..services.preview_service import build_preview_url_path
from ..services.storage_capacity_service import InsufficientDiskSpaceError, check_free_disk_space
from ..services.wallet_service import InsufficientCreditsError


def _apply_project_status(db: Session, project: Project, failure_reason: str | None = None) -> str:
    """Recomputes and applies `project.status` from every enabled tier's
    latest preview job -- the shared tail of both the success and failure
    paths below, so one tier failing can never stomp a sibling tier's
    delivered output (see generation_status_service for the rules).

    `failure_reason` is only surfaced project-wide when *every* enabled
    tier failed; a partial failure reports per tier instead, and a
    successful retry clears a stale reason left by an earlier attempt.
    """
    db.flush()
    enabled_tier_keys = {enabled_tier.key for enabled_tier in tier_service.get_enabled_tiers(db)}
    outcomes = generation_status_service.get_preview_tier_outcomes(db, project.id)
    status = generation_status_service.resolve_project_status(enabled_tier_keys, outcomes)
    project.status = status
    project.rejection_reason = failure_reason if status == "failed" else None
    return status


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
            candidate_templates = prompt_template_service.filter_templates_by_category(
                candidate_templates, blueprint_row.site_category
            )
            result = generate_site(
                project_root,
                tier,
                generation_model=generation_model,
                candidate_templates=candidate_templates,
            )
        except Exception as exc:
            # Most failures here are an OpenRouterError, whose message is
            # written for debugging (it embeds raw API response bodies or
            # model output), not for an end user -- see app/errors.py.
            message = user_facing_message(
                exc, "Something went wrong while generating this tier. Please try again."
            )
            job.overall_status = "failed"
            job.failure_reason = message
            job.finished_at = datetime.now(timezone.utc)
            # This tier is done for, but its siblings' output stands -- the
            # project only goes "failed" if every enabled tier failed. The
            # user retries just this tier via POST /projects/{id}/retry-tier.
            _apply_project_status(db, project, failure_reason=message)
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
        # concurrently on different queue workers, so the project's status is
        # recomputed from every tier's latest outcome rather than from chain
        # position -- correct regardless of which tier finishes last, and of
        # whether any of them failed.
        _apply_project_status(db, project)

        db.commit()
        return result
    finally:
        db.close()
