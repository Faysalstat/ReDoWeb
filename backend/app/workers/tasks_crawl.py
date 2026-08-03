import uuid

from ..crawler.errors import CrawlRejected
from ..db.session import SessionLocal
from ..models import Asset, CrawlPage, CrawlSnapshot, Project
from ..services.crawl_service import run_crawl
from .celery_app import celery_app


@celery_app.task(bind=True)
def run_crawl_task(self, project_id: str, url: str) -> str:
    """First link in the submission chain. On any failure the project is
    left in a terminal ('rejected' or 'failed') DB state and the exception
    is re-raised so the chain halts here -- Celery chains don't proceed to
    the next task once one fails, which is exactly the "don't charge/don't
    continue on a definitive failure" behavior we want.

    No auto-retry in this pass (see docs/PROGRESS.md) -- a bare exception
    always resolves to a visible terminal state rather than a half-built
    retry policy that could leave a project stuck in "crawling" forever.
    """
    db = SessionLocal()
    try:
        project = db.get(Project, uuid.UUID(project_id))
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
        db.commit()
        return project_id
    finally:
        db.close()
