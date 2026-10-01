import uuid
from pathlib import Path

from ..ai.blueprint_pipeline import run_blueprint_pipeline
from ..config import get_settings
from ..db.session import SessionLocal
from ..errors import user_facing_message
from ..models import Blueprint, Project
from ..services import (
    cost_estimation_service,
    cost_settings_service,
    model_config_service,
    prompt_template_service,
    token_usage_service,
)
from ..services.blueprint_service import build_blueprint_row
from .queue import enqueue


def _apply_cost_gate(
    project,
    tier_keys: list[str],
    estimate: cost_estimation_service.GenerationCostEstimate,
    alert_threshold_usd: float,
) -> bool:
    """Mutates `project`'s status/estimate fields when the estimated total
    cost exceeds `alert_threshold_usd`, and returns whether it did --
    extract_blueprint_task skips the generate_tier fan-out when True instead
    (see docs/generation-cost-gate-plan.md). Pure aside from that mutation,
    so it's unit-testable with a plain fake project object -- no AI call or
    real DB session needed (mirrors tasks_full_site._merge_full_blueprint's
    extract-the-pure-decision testing style)."""
    if estimate.total_estimated_cost_usd <= alert_threshold_usd:
        return False
    project.status = "awaiting_cost_approval"
    project.estimated_generation_cost_usd = estimate.total_estimated_cost_usd
    project.pending_tier_keys = tier_keys
    return True


def extract_blueprint_task(project_id: str, tier_keys: list[str]) -> str:
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))
        project.status = "extracting_blueprint"
        db.commit()

        vision_model = model_config_service.get_vision_model(db)
        available_categories = prompt_template_service.get_active_template_categories(db)
        try:
            # Initial pipeline run: AI-review only the home page (index 0)
            # regardless of how many pages were crawled -- keeps preview
            # AI-review cost matched to what site_generator.generate_site()
            # actually uses today. The rest of a multi-page crawl's pages
            # are reviewed later, lazily, only if/when a user pays to
            # download a full multi-page site (see tasks_full_site.py).
            result = run_blueprint_pipeline(
                project_root,
                vision_model=vision_model,
                page_indices=[0],
                include_meta=True,
                available_categories=available_categories,
            )
        except Exception as exc:
            # Most failures here are an OpenRouterError, whose message is
            # written for debugging (it embeds raw API response bodies or
            # model output), not for an end user -- see app/errors.py.
            project.status = "failed"
            project.rejection_reason = user_facing_message(
                exc, "Something went wrong while analyzing your site. Please try again."
            )
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

        # Cost gate (see docs/generation-cost-gate-plan.md): estimate the
        # total USD cost of generating every enabled tier from the
        # design.md this run just produced, *before* fanning out any
        # generate_tier job. Over the admin-configurable threshold, pause
        # the pipeline for the user's approval instead of enqueueing --
        # nothing sits in the queue while unapproved, so this needs no new
        # locking against the concurrent queue workers.
        design_md_path = project_root / "blueprint" / "design.md"
        design_md = design_md_path.read_text(encoding="utf-8")
        estimate = cost_estimation_service.estimate_generation_cost(db, tier_keys, design_md)
        alert_threshold_usd = cost_settings_service.get_generation_cost_alert_usd(db)

        if not _apply_cost_gate(project, tier_keys, estimate, alert_threshold_usd):
            # Fan out: every enabled tier's generate_tier job is enqueued
            # here, up front, instead of chaining one at a time. Multiple
            # queue workers (see docs/concurrency-scaling-plan.md) can then
            # claim and run them concurrently, and each tier now succeeds or
            # fails independently -- previously, one tier raising meant
            # every tier after it in the chain silently never even
            # attempted to run.
            for tier_key in tier_keys:
                enqueue(db, "generate_tier", {"project_id": project_id, "tier": tier_key})

        db.commit()
        return project_id
    finally:
        db.close()
