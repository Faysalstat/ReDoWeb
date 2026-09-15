import uuid

from ..models import Blueprint


def build_blueprint_row(project_id: uuid.UUID, version: int, result: dict) -> Blueprint:
    """Builds an unsaved Blueprint row from a run_blueprint_pipeline() result
    dict -- shared by routers/blueprint.py (debug route) and
    workers/tasks_blueprint.py (real queue task handler) so the two call
    sites don't duplicate this field mapping."""
    meta = result["blueprint"]["meta"]
    return Blueprint(
        project_id=project_id,
        version=version,
        source="ai_extracted",
        design_md_storage_path=result["design_md_path"],
        scraped_json_storage_path=result["scraped_json_path"],
        blueprint_json_storage_path=result["blueprint_json_path"],
        site_name=meta.get("site_name"),
        tagline=meta.get("tagline"),
        colors=meta.get("colors"),
        logo_path=meta.get("logo"),
        favicon_path=meta.get("favicon"),
        fonts=meta.get("fonts"),
        tone=meta.get("tone"),
        is_current=True,
    )
