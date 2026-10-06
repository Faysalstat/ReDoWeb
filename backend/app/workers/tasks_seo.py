import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..ai.blueprint_schema import BlueprintDocument
from ..ai.errors import GenerationError, IterationLimitError
from ..ai.postprocess import PLACEHOLDER_ORIGIN, site_origin_from_url
from ..ai.seo_agent import SEO_STEPS, run_seo_pass
from ..ai.site_generator import _rmtree_with_retry
from ..config import get_settings
from ..db.session import SessionLocal
from ..errors import user_facing_message
from ..models import GenerationJob, GenerationOutput, Project
from ..services import model_config_service, token_usage_service
from ..services.job_progress import JobProgress, Step
from ..services.preview_service import build_preview_url_path
from ..services.storage_capacity_service import check_free_disk_space

logger = logging.getLogger(__name__)

# Never copied into seo/: sibling build outputs and internal artifacts.
_SKIP_TOP_LEVEL_DIRS = {"full", "seo"}


def _latest_succeeded_output(db, project_id: uuid.UUID, tier: str, scope: str) -> GenerationOutput | None:
    job = (
        db.query(GenerationJob)
        .filter(
            GenerationJob.project_id == project_id,
            GenerationJob.tier == tier,
            GenerationJob.scope == scope,
            GenerationJob.overall_status == "succeeded",
        )
        .order_by(GenerationJob.created_at.desc())
        .first()
    )
    return job.output if job is not None else None


def copy_site_for_seo(source_dir: Path, seo_dir: Path) -> int:
    """Copies the finished site (full/ or the single-page preview) into
    seo/, skipping sibling build folders and debug traces -- the SEO pass
    only ever edits this copy, so the output it came from stays
    downloadable whatever happens here."""
    if seo_dir.exists():
        _rmtree_with_retry(seo_dir)
    seo_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in sorted(source_dir.rglob("*")):
        rel = src.relative_to(source_dir)
        if len(rel.parts) > 1 and rel.parts[0] in _SKIP_TOP_LEVEL_DIRS:
            continue
        if not src.is_file() or src.name.startswith("_debug_trace"):
            continue
        dest = seo_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        copied += 1
    return copied


def run_seo_task(project_id: str, tier: str, job_id: str) -> dict:
    """Post-purchase "Run SEO agent" for Pro/Premium (see
    routers/downloads.py's start_seo, which created this job row under a
    Project row lock before enqueueing, and checked purchase + tier +
    "all pages generated first"). Like generate_full_site_task, this never
    touches Project.status -- it's an enrichment of an already-"ready"
    project, not part of the main pipeline."""
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    progress = JobProgress(
        job_id,
        [Step(*step) for step in SEO_STEPS],
        context=f"[seo job={job_id} project={project_id} tier={tier}]",
    )
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))
        job = db.get(GenerationJob, uuid.UUID(job_id))

        try:
            progress.start_step("prepare")
            check_free_disk_space()

            source = _latest_succeeded_output(db, project.id, tier, "full_site") or _latest_succeeded_output(
                db, project.id, tier, "preview"
            )
            if source is None:
                raise GenerationError(f"No finished '{tier}' site found to optimize")
            source_dir = project_root / source.output_storage_path
            if not (source_dir / "index.html").exists():
                raise GenerationError("The finished site's files are missing on disk")

            seo_dir = project_root / "generated" / tier / "seo"
            copied = copy_site_for_seo(source_dir, seo_dir)
            source_kind = "all pages" if source.job.scope == "full_site" else "the single-page site"
            progress.log(f"Working on a copy of {source_kind} ({copied} file(s)); the original stays untouched")

            blueprint = BlueprintDocument.model_validate(
                json.loads((project_root / "blueprint" / "blueprint.json").read_text(encoding="utf-8"))
            )
            metadata = json.loads((project_root / "metadata.json").read_text(encoding="utf-8"))
            site_origin = site_origin_from_url(metadata.get("source_url") or project.source_url) or PLACEHOLDER_ORIGIN

            generation_model = model_config_service.get_generation_model(tier, db)
            progress.log(f"Public address: {site_origin} · model: {generation_model}", "debug")
            result = run_seo_pass(
                seo_dir,
                blueprint=blueprint,
                site_origin=site_origin,
                generation_model=generation_model,
                progress=progress,
            )
        except Exception as exc:
            if isinstance(exc, IterationLimitError):
                # Only reached when the agent made no edits at all (partial
                # progress is kept by run_seo_pass) -- the raw "did not
                # finish within N iterations" isn't meaningful to a user.
                message = "The SEO agent couldn't finish this time. Please try again."
            else:
                message = user_facing_message(
                    exc, "Something went wrong while optimizing this site for search. Please try again."
                )
            # The full error (often an OpenRouter body) goes to the worker log
            # and the admin-only debug entry, never into the user-facing text.
            logger.exception("%s failed: %s", progress.context, exc)
            progress.log(f"Error: {str(exc)[:300]}", "debug")
            progress.fail(message)
            job.overall_status = "failed"
            job.failure_reason = message
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise

        progress.start_step("save")

        db.add(
            GenerationOutput(
                job_id=job.id,
                template_used=source.template_used,
                output_storage_path=seo_dir.relative_to(project_root).as_posix(),
                preview_url_path=build_preview_url_path(project_id, seo_dir.relative_to(project_root).as_posix()),
                summary=result["summary"],
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"],
                iterations=result["iterations"],
                sitemap_written=True,
                seo_report=result["report"],
            )
        )
        # purpose="seo", never "generation": cost_estimation_service's
        # preview calibration filters on purpose == "generation" and must
        # not be skewed by SEO runs.
        usage_row = token_usage_service.record_usage(
            db,
            project_id=project.id,
            user_id=project.user_id,
            job_id=job.id,
            model_name=result["model"],
            purpose="seo",
            prompt_tokens=result["usage"]["prompt_tokens"],
            completion_tokens=result["usage"]["completion_tokens"],
        )
        progress.log(
            f"Tokens: {result['usage']['prompt_tokens']} in / {result['usage']['completion_tokens']} out "
            f"· est. ${usage_row.cost_estimate_usd:.4f} · {result['iterations']} step(s)",
            "debug",
        )

        job.overall_status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        report = result["report"]
        progress.succeed(
            f"{report.get('edits', 0)} edit(s) on {len(report.get('pages_edited', []))} page(s) · "
            "sitemap, robots.txt and llms.txt added"
            + (" · AI pass stopped at its step limit; some pages were only auto-fixed" if report.get("agent_stopped_early") else "")
        )
        return {"output_dir": seo_dir.relative_to(project_root).as_posix(), "report": result["report"]}
    finally:
        db.close()
