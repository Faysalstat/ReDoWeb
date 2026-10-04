import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..ai.blueprint_legacy_compat import render_design_md_compat
from ..ai.blueprint_review import review_blueprint
from ..ai.blueprint_schema import BlueprintDocument
from ..ai.errors import GenerationError
from ..ai.site_generator import generate_full_site
from ..config import get_settings
from ..db.session import SessionLocal
from ..models import Blueprint, GenerationJob, GenerationOutput, Project
from ..services import model_config_service, token_usage_service
from ..services.blueprint_service import build_blueprint_row
from ..services.preview_service import build_preview_url_path


def _merge_full_blueprint(
    home_blueprint: BlueprintDocument, remaining_reviewed: BlueprintDocument
) -> BlueprintDocument:
    """Combines the already-reviewed home page (blueprint.pages[0], from
    the initial pipeline run) with the newly-reviewed remaining pages, in
    original crawl order. meta/navigation always come from
    `home_blueprint` -- already resolved (and possibly AI-corrected) by
    the original run; `remaining_reviewed`'s were left untouched
    (reviewed with include_meta=False) and are never the source of truth
    here."""
    merged = home_blueprint.model_copy(deep=True)
    merged.pages = home_blueprint.pages + remaining_reviewed.pages
    return merged


def generate_full_site_task(project_id: str, tier: str, job_id: str) -> dict:
    """Triggered lazily by routers/downloads.py on first download/purchase
    of a tier for a project with more than one crawled page, then cached --
    a later download of the same (project, tier) reuses the result on disk
    without re-running this. Unlike other queue tasks, the GenerationJob
    row already exists (scope="full_site") by the time this runs: the
    router creates it synchronously, under a Project row lock, before
    enqueueing, so a second concurrent download click sees "already
    running" instead of racing to create a duplicate job (see
    downloads.py's start_download).

    Deliberately does NOT touch Project.status -- the project is already
    "ready" from the original preview pipeline; this is a background
    enrichment triggered by a download click, not part of the main
    crawl -> blueprint -> generate chain, so it shouldn't regress that
    terminal state on failure.
    """
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))
        job = db.get(GenerationJob, uuid.UUID(job_id))

        try:
            current_blueprint_row = (
                db.query(Blueprint)
                .filter(Blueprint.project_id == project.id, Blueprint.is_current.is_(True))
                .one_or_none()
            )
            if current_blueprint_row is None:
                raise GenerationError("No blueprint found for this project")

            current_blueprint = BlueprintDocument.model_validate(
                json.loads(
                    (project_root / current_blueprint_row.blueprint_json_storage_path).read_text(encoding="utf-8")
                )
            )
            scraped = BlueprintDocument.model_validate(
                json.loads(
                    (project_root / current_blueprint_row.scraped_json_storage_path).read_text(encoding="utf-8")
                )
            )

            if len(current_blueprint.pages) < len(scraped.pages):
                # Still home-page-only -- AI-review the remaining pages
                # once, project-wide (not per tier): a second tier's
                # full-site download for the same project will find
                # len(pages) == len(scraped.pages) here and skip straight
                # to generation below, without re-reviewing anything.
                vision_model = model_config_service.get_vision_model(db)
                remaining_indices = list(range(1, len(scraped.pages)))
                remaining_reviewed, usage = review_blueprint(
                    project_root,
                    scraped,
                    model=vision_model,
                    page_indices=remaining_indices,
                    include_meta=False,
                )
                full_blueprint = _merge_full_blueprint(current_blueprint, remaining_reviewed)

                # Fixed paths, always overwritten in place -- matches the
                # existing blueprint_pipeline.py convention (see its own
                # docstring: "no versioned subfolders"). Only the DB row
                # below is versioned.
                blueprint_dir = project_root / "blueprint"
                (blueprint_dir / "blueprint.json").write_text(
                    json.dumps(full_blueprint.model_dump(mode="json"), indent=2), encoding="utf-8"
                )
                (blueprint_dir / "design.md").write_text(
                    render_design_md_compat(full_blueprint), encoding="utf-8"
                )

                token_usage_service.record_usage(
                    db,
                    project_id=project.id,
                    user_id=project.user_id,
                    job_id=job.id,
                    model_name=vision_model,
                    purpose="blueprint_extraction_full_site",
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                )

                db.query(Blueprint).filter(
                    Blueprint.project_id == project.id, Blueprint.is_current.is_(True)
                ).update({"is_current": False})
                next_version = db.query(Blueprint).filter(Blueprint.project_id == project.id).count() + 1
                db.add(
                    build_blueprint_row(
                        project.id,
                        next_version,
                        {
                            "scraped_json_path": current_blueprint_row.scraped_json_storage_path,
                            "blueprint_json_path": current_blueprint_row.blueprint_json_storage_path,
                            "design_md_path": current_blueprint_row.design_md_storage_path,
                            "blueprint": full_blueprint.model_dump(mode="json"),
                        },
                    )
                )
                db.flush()

            # Anchor to the ORIGINAL preview job's pinned template + cached
            # index.html/style.css (read directly off disk inside
            # generate_full_site()) -- never re-rolls the random template
            # choice for the additional pages.
            preview_job = (
                db.query(GenerationJob)
                .filter(
                    GenerationJob.project_id == project.id,
                    GenerationJob.tier == tier,
                    GenerationJob.scope == "preview",
                    GenerationJob.overall_status == "succeeded",
                )
                .order_by(GenerationJob.created_at.desc())
                .first()
            )
            if preview_job is None or preview_job.output is None:
                raise GenerationError(f"No succeeded preview generation found for tier '{tier}'")

            generation_model = model_config_service.get_generation_model(tier, db)
            result = generate_full_site(
                project_root,
                tier,
                template_override=preview_job.output.template_used,
                generation_model=generation_model,
            )
        except Exception as exc:
            job.overall_status = "failed"
            job.failure_reason = str(exc)
            job.finished_at = datetime.now(timezone.utc)
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
            purpose="full_site_generation",
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=result["usage"]["completion_tokens"],
        )

        job.overall_status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return result
    finally:
        db.close()
