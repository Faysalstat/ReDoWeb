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
from .design_system_generation import generate_design_system


def run_blueprint_pipeline(project_root: Path) -> dict:
    scraped = extract_scraped_json(project_root)

    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True, exist_ok=True)

    scraped_json_path = blueprint_dir / "scraped.json"
    scraped_json_path.write_text(
        json.dumps(scraped.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    blueprint, usage = review_blueprint(project_root, scraped)

    blueprint_json_path = blueprint_dir / "blueprint.json"
    blueprint_json_path.write_text(
        json.dumps(blueprint.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    # Runs once per project (not once per tier) -- every enabled tier's
    # generation call reads the same design_system.json. See
    # design_system_generation.py for why this is a separate AI step
    # instead of folded into site_generator.py's per-tier agent loop.
    design_system, design_system_usage = generate_design_system(blueprint)
    usage["prompt_tokens"] += design_system_usage.get("prompt_tokens", 0)
    usage["completion_tokens"] += design_system_usage.get("completion_tokens", 0)

    design_system_path = blueprint_dir / "design_system.json"
    design_system_path.write_text(
        json.dumps(design_system, indent=2), encoding="utf-8"
    )

    design_md_path = blueprint_dir / "design.md"
    design_md_path.write_text(render_design_md_compat(blueprint), encoding="utf-8")

    return {
        "scraped_json_path": scraped_json_path.relative_to(project_root).as_posix(),
        "blueprint_json_path": blueprint_json_path.relative_to(project_root).as_posix(),
        "design_system_json_path": design_system_path.relative_to(project_root).as_posix(),
        "design_md_path": design_md_path.relative_to(project_root).as_posix(),
        "blueprint": blueprint.model_dump(mode="json"),
        "design_system": design_system,
        "usage": usage,
    }
