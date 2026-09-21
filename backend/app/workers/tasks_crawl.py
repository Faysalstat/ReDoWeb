import uuid

from ..crawler.errors import CrawlRejected
from ..db.session import SessionLocal
from ..models import Asset, CrawlPage, CrawlSnapshot, Project
from ..services.crawl_service import run_crawl
from ..services.storage_capacity_service import InsufficientDiskSpaceError, check_free_disk_space
from .queue import enqueue


def run_crawl_task(project_id: str, url: str, tier_keys: list[str]) -> str:
    """First stage in the submission pipeline. On any failure the project is
    left in a terminal ('rejected' or 'failed') DB state and the exception
    is re-raised so queue_worker.py halts the pipeline here -- nothing
    further gets enqueued once a stage fails, which is exactly the "don't
    charge/don't continue on a definitive failure" behavior we want.

    No auto-retry in this pass (see docs/PROGRESS.md) -- a bare exception
    always resolves to a visible terminal state rather than a half-built
    retry policy that could leave a project stuck in "crawling" forever.
    """
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

        project.status = "crawling"
        db.commit()

        try:
            result = run_crawl(uuid.UUID(project_id), url)
        except CrawlRejected as exc:
            project.status = "rejected"
            project.rejection_reason = exc.message
            db.commit()
            raise
        except Exception as exc:
            project.status = "failed"
            project.rejection_reason = getattr(exc, "message", str(exc))
            db.commit()
            raise

        snapshot = CrawlSnapshot(project_id=project.id, page_count=result["page_count"])
        db.add(snapshot)
        db.flush()

        for page in result["pages"]:
            db.add(
                CrawlPage(
                    snapshot_id=snapshot.id,
                    url=page["url"],
                    http_status=page["http_status"],
                    storage_path=page["storage_path"],
                )
            )

        for asset in result["assets"]:
            db.add(
                Asset(
                    project_id=project.id,
                    asset_type=asset["asset_type"],
                    original_url=asset["original_url"],
                    storage_path=asset["storage_path"],
                    content_type=asset.get("content_type"),
                )
            )

        project.status = "crawled"
        enqueue(db, "extract_blueprint", {"project_id": project_id, "tier_keys": tier_keys})
        db.commit()
        return project_id
    finally:
        db.close()
