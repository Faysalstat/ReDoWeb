"""Orchestration entry point for the structured JSON blueprint pipeline --
the direct replacement for the old blueprint_extractor.extract_blueprint().
See docs/blueprint-json-pipeline-plan.md.

Fixed paths, always overwritten (no versioned subfolders) -- matches the
existing pre-pipeline behavior and keeps site_generator.py's hardcoded
`blueprint/design.md` path working via the compat shim.
"""

import json
from pathlib import Path

from .blueprint_extraction import extract_scraped_json
from .blueprint_legacy_compat import render_design_md_compat
from .blueprint_review import review_blueprint


def run_blueprint_pipeline(
    project_root: Path,
    vision_model: str | None = None,
    page_indices: list[int] | None = None,
    include_meta: bool = True,
) -> dict:
    """`vision_model` overrides the OpenRouter model id used for every AI
    call in this pipeline (blueprint review's meta/content/gap-check calls)
    -- real callers (tasks_blueprint.py) resolve it once from the DB-backed
    model_config_service.get_vision_model() and pass it in; omitted, it
    falls back to config.py's static vision_model default (used by the
    DB-free /api/v1/debug/* routes).

    `page_indices`/`include_meta` pass straight through to
    review_blueprint() -- see its docstring. Defaults (None/True) preserve
    full-document review for any caller that doesn't pass them. The real
    pipeline's initial run (tasks_blueprint.py) passes `page_indices=[0]`
    so AI-review cost only ever scales with the home page, regardless of
    how many pages were crawled; `scraped.json` below still captures every
    crawled page's deterministic extraction, unused until a later
    full-site purchase (tasks_full_site.py) reviews the rest."""
    scraped = extract_scraped_json(project_root)

    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True, exist_ok=True)

    scraped_json_path = blueprint_dir / "scraped.json"
    scraped_json_path.write_text(
        json.dumps(scraped.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    blueprint, usage = review_blueprint(
        project_root, scraped, model=vision_model, page_indices=page_indices, include_meta=include_meta
    )

    blueprint_json_path = blueprint_dir / "blueprint.json"
    blueprint_json_path.write_text(
        json.dumps(blueprint.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    design_md_path = blueprint_dir / "design.md"
    design_md_path.write_text(render_design_md_compat(blueprint), encoding="utf-8")

    return {
        "scraped_json_path": scraped_json_path.relative_to(project_root).as_posix(),
        "blueprint_json_path": blueprint_json_path.relative_to(project_root).as_posix(),
        "design_md_path": design_md_path.relative_to(project_root).as_posix(),
        "blueprint": blueprint.model_dump(mode="json"),
        "usage": usage,
    }
