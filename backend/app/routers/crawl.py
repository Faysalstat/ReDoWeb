import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..crawler.errors import CrawlError, CrawlRejected
from ..db.session import get_db
from ..models import Asset, CrawlPage, CrawlSnapshot, Project, SubmissionLog
from ..schemas.crawl import CrawlRequest, CrawlResponse
from ..services.crawl_service import run_crawl

router = APIRouter(prefix="/api/v1", tags=["crawl"])


@router.post("/crawl", response_model=CrawlResponse)
def submit_crawl(payload: CrawlRequest, request: Request, db: Session = Depends(get_db)) -> CrawlResponse:
    client_ip = request.client.host if request.client else None

    project = Project(
        source_url=str(payload.url),
        tos_accepted=payload.tos_accepted,
        submitted_ip=client_ip,
        status="crawling",
    )
    db.add(project)
    db.flush()  # assigns project.id without committing yet

    db.add(
        SubmissionLog(
            project_id=project.id,
            url=str(payload.url),
            ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            tos_accepted=payload.tos_accepted,
        )
    )
    db.commit()

    try:
        result = run_crawl(project.id, str(payload.url))
    except CrawlRejected as exc:
        project.status = "rejected"
        project.rejection_reason = exc.message
        db.commit()
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except CrawlError as exc:
        project.status = "failed"
        project.rejection_reason = exc.message
        db.commit()
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except httpx.HTTPError as exc:
        # Network-level failure (DNS, timeout, connection refused, etc.) --
        # this slice has no retry layer yet, so surface it the same way as
        # a definitive SiteInaccessible failure rather than a 500.
        project.status = "failed"
        project.rejection_reason = str(exc)
        db.commit()
        raise HTTPException(
            status_code=422, detail=f"Could not reach the site: {exc}"
        ) from exc

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

    return CrawlResponse(**result)
