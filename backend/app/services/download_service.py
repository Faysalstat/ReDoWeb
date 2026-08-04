import shutil
from pathlib import Path

from ..config import get_settings


def build_download_zip(project_id: str, tier_key: str, output_storage_path: str) -> Path:
    """Zips the generated output folder for one tier into
    {storage_root}/projects/{project_id}/downloads/{tier_key}.zip, overwriting
    any previous archive for that tier -- output is overwritten in place on
    every generate_tier_task run (see site_generator.generate_site), so a
    stale zip would silently serve old content otherwise."""
    settings = get_settings()
    project_root = Path(settings.storage_root) / "projects" / project_id
    output_dir = project_root / output_storage_path
    downloads_dir = project_root / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    archive_base = downloads_dir / tier_key
    archive_path = archive_base.with_suffix(".zip")
    if archive_path.exists():
        archive_path.unlink()

    shutil.make_archive(str(archive_base), "zip", root_dir=output_dir)
    return archive_path
