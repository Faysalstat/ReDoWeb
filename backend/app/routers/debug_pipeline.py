"""Debug-only, database-free HTTP endpoints for exercising the pipeline
stages independently (scrape / review / design-system / design-md /
generate), per docs/blueprint-pipeline-experiment-plan.md. Same spirit as
the existing deprecated debug routes on crawl/blueprint/generation -- not
part of the real product flow (no DB rows, no credit spend), just a fast
way to manually test one stage at a time via /docs without needing
Postgres, Redis, or the Celery worker running. /generate calls the real,
shared site_generator.generate_site() -- same function the product routes
use.
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..ai.blueprint_extraction import extract_scraped_json
from ..ai.blueprint_legacy_compat import render_design_md_compat
from ..ai.blueprint_review import review_blueprint
from ..ai.blueprint_schema import BlueprintDocument
from ..ai.design_system_generation import RECIPES_DIR, generate_design_system
from ..ai.errors import BlueprintExtractionError, GenerationError
from ..ai.site_generator import generate_site
from ..config import get_settings
from ..crawler.errors import CrawlError
from ..schemas.crawl import CrawlRequest
from ..services.crawl_service import run_crawl

router = APIRouter(prefix="/api/v1/debug", tags=["debug-pipeline"])


def _validate_project_id(project_id: str) -> None:
    """These routes build filesystem paths directly from `project_id` with
    no DB-backed existence check (unlike the real product routes) -- reject
    anything that isn't a well-formed UUID before it ever reaches a Path,
    so a path-traversal payload (e.g. `..%2f..%2fsome-dir`) can't escape
    storage_root/projects/."""
    try:
        uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid project_id: {project_id}")

# Last project with a full scraped.json + blueprint.json from manual
# testing (2026-08-26, fix2live.com) -- used as the default project_id for
# the /generate debug endpoint so it doesn't need to be typed in every time.
# Update this once you're testing against a different project.
LAST_TESTED_PROJECT_ID = "1eb4f080-e14c-41d7-aa78-968fbc0550be"


@router.post("/scrape")
def debug_scrape(payload: CrawlRequest) -> dict:
    """Stage 1 only: crawls `url` and runs the deterministic (no-AI, free)
    extractor, writing blueprint/scraped.json to disk. Returns the
    generated project_id so stage 2/3 can find the same project folder --
    no database row is created."""
    project_id = uuid.uuid4()
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / str(project_id)

    try:
        run_crawl(project_id, str(payload.url))
    except CrawlError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    try:
        scraped = extract_scraped_json(project_root)
    except BlueprintExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    scraped_dict = scraped.model_dump(mode="json")
    (blueprint_dir / "scraped.json").write_text(json.dumps(scraped_dict, indent=2), encoding="utf-8")

    return {"project_id": str(project_id), "scraped": scraped_dict}


@router.post("/review/{project_id}")
def debug_review(project_id: str) -> dict:
    """Stage 2 only: reads that project's blueprint/scraped.json (from
    stage 1) and runs the AI review, writing blueprint/blueprint.json.
    Makes real, billed OpenRouter calls -- requires
    REDOWEBS_OPENROUTER_API_KEY to be set."""
    _validate_project_id(project_id)
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    scraped_path = project_root / "blueprint" / "scraped.json"
    if not scraped_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No scraped.json found for project {project_id} -- run POST /debug/scrape first",
        )

    scraped = BlueprintDocument.model_validate(json.loads(scraped_path.read_text(encoding="utf-8")))
    blueprint, usage = review_blueprint(project_root, scraped)

    blueprint_dict = blueprint.model_dump(mode="json")
    (project_root / "blueprint" / "blueprint.json").write_text(
        json.dumps(blueprint_dict, indent=2), encoding="utf-8"
    )

    return {"project_id": project_id, "blueprint": blueprint_dict, "usage": usage}


@router.post("/design-system/{project_id}")
def debug_design_system(project_id: str, recipe_override: str | None = None) -> dict:
    """Stage 2.5: reads that project's blueprint/blueprint.json (falling
    back to scraped.json if review hasn't been run yet) and runs the
    design-system-generation AI step, writing blueprint/design_system.json
    -- the same step run_blueprint_pipeline() runs automatically, exposed
    here for repeatable manual testing of one specific recipe anchor.
    `recipe_override` (a name from backend/prompts/recipes/, e.g. "linear")
    forces that recipe as the sole candidate instead of the deterministic
    tone-keyword pre-filter -- the call still goes through the AI step, it
    just skips the pre-filter. Makes real, billed OpenRouter calls --
    requires REDOWEBS_OPENROUTER_API_KEY to be set."""
    _validate_project_id(project_id)
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    blueprint_dir = project_root / "blueprint"

    source_path = blueprint_dir / "blueprint.json"
    if not source_path.exists():
        source_path = blueprint_dir / "scraped.json"
    if not source_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No scraped.json or blueprint.json found for project {project_id}",
        )

    candidates = None
    if recipe_override:
        if not (RECIPES_DIR / f"{recipe_override}.md").exists():
            raise HTTPException(status_code=400, detail=f"Unknown recipe: {recipe_override}")
        candidates = [recipe_override]

    blueprint = BlueprintDocument.model_validate(json.loads(source_path.read_text(encoding="utf-8")))
    design_system, usage = generate_design_system(blueprint, candidates=candidates)

    (blueprint_dir / "design_system.json").write_text(
        json.dumps(design_system, indent=2), encoding="utf-8"
    )

    return {"project_id": project_id, "design_system": design_system, "usage": usage}


@router.post("/design-md/{project_id}")
def debug_render_design_md(project_id: str) -> dict:
    """Stage 3 prep: regenerates blueprint/design.md from blueprint.json
    (falling back to scraped.json if review hasn't been run yet), so the
    existing, unchanged site_generator.py can build against manually
    produced pipeline output."""
    _validate_project_id(project_id)
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    blueprint_dir = project_root / "blueprint"

    source_path = blueprint_dir / "blueprint.json"
    if not source_path.exists():
        source_path = blueprint_dir / "scraped.json"
    if not source_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No scraped.json or blueprint.json found for project {project_id}",
        )

    document = BlueprintDocument.model_validate(json.loads(source_path.read_text(encoding="utf-8")))
    design_md = render_design_md_compat(document)
    (blueprint_dir / "design.md").write_text(design_md, encoding="utf-8")

    return {"project_id": project_id, "source": source_path.name, "design_md": design_md}


@router.post("/generate")
def debug_generate(
    project_id: str = LAST_TESTED_PROJECT_ID,
    tier: str = "pro",
) -> dict:
    """Stage 3: calls the REAL site_generator.generate_site() -- the exact
    function the product's real routes/Celery task use. Makes real, billed
    OpenRouter calls against REDOWEBS_GENERATION_MODEL. Regenerates
    blueprint/design.md from blueprint.json first (so it reflects the
    latest review, not whatever design.md happened to be on disk). Reads
    blueprint/design_system.json if present (run POST /debug/design-system
    first to control which recipe anchor it uses); generate_site() falls
    back to a deterministic default if it's missing, same as a real run
    would. Output goes to blueprint/../generated/{tier}/ (index.html,
    style.css, copies of design.md/blueprint.json/design_system.json, and
    _debug_trace.json) inside that project's folder -- same output shape a
    real generation run produces. project_id defaults to the last
    manually-tested project so it doesn't need to be re-typed every run."""
    _validate_project_id(project_id)
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")

    blueprint_dir = project_root / "blueprint"
    source_path = blueprint_dir / "blueprint.json"
    if not source_path.exists():
        source_path = blueprint_dir / "scraped.json"
    if not source_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No scraped.json or blueprint.json found for project {project_id}",
        )
    document = BlueprintDocument.model_validate(json.loads(source_path.read_text(encoding="utf-8")))
    (blueprint_dir / "design.md").write_text(render_design_md_compat(document), encoding="utf-8")

    try:
        result = generate_site(project_root, tier)
    except GenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"project_id": project_id, **result}
