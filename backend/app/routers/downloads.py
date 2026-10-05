import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..db.session import get_db
from ..models import CrawlSnapshot, GenerationJob, Project, User
from ..schemas.download import DownloadStartResponse, DownloadStatusResponse
from ..services import tier_service, wallet_service
from ..services.download_service import build_download_zip
from ..services.wallet_service import InsufficientCreditsError
from ..workers.queue import enqueue

router = APIRouter(prefix="/api/v1", tags=["downloads"])


def _get_owned_project(db: Session, project_id: str, current_user: User) -> Project:
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or project.user_id != current_user.id:
        # Same 404 for "doesn't exist" and "not yours" as GET /projects/{id}.
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")
    return project


def _latest_page_count(db: Session, project_id: uuid.UUID) -> int:
    snapshot = (
        db.query(CrawlSnapshot)
        .filter(CrawlSnapshot.project_id == project_id)
        .order_by(CrawlSnapshot.crawl_finished_at.desc())
        .first()
    )
    # Defensive fallback only -- a project that's reached "ready" always has
    # a snapshot; this just avoids a crash if that invariant is ever broken.
    return snapshot.page_count if snapshot is not None else 1


def _latest_full_site_job(db: Session, project_id: uuid.UUID, tier: str) -> GenerationJob | None:
    return (
        db.query(GenerationJob)
        .filter(
            GenerationJob.project_id == project_id,
            GenerationJob.tier == tier,
            GenerationJob.scope == "full_site",
        )
        .order_by(GenerationJob.created_at.desc())
        .first()
    )


def _resolve_download_plan(
    page_count: int, full_site_job: GenerationJob | None
) -> Literal["fast_path", "already_building", "start_build"]:
    """Pure decision function, kept separate from the DB/router plumbing so
    it's directly unit-testable. `page_count <= 1` (single-page project) is
    always the fast path, matching today's instant-zip behavior exactly --
    a full-site build is never needed for a project that only ever crawled
    one page. Otherwise: no full-site job yet -> start one; one already
    `running` -> don't duplicate it; one `succeeded` -> reuse it (the fast
    path); one `failed` -> allow a fresh attempt (no extra charge, since
    the download_spend idempotency key was already spent on first
    download regardless of outcome)."""
    if page_count <= 1:
        return "fast_path"
    if full_site_job is None:
        return "start_build"
    if full_site_job.overall_status == "running":
        return "already_building"
    if full_site_job.overall_status == "succeeded":
        return "fast_path"
    return "start_build"


@router.post("/projects/{project_id}/download", response_model=DownloadStartResponse)
def start_download(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadStartResponse:
    project = _get_owned_project(db, project_id, current_user)

    tier_info = tier_service.get_tier(tier)
    if tier_info is None or not tier_info.is_active:
        raise HTTPException(status_code=400, detail=f"Unknown or disabled tier '{tier}'")

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
        raise HTTPException(status_code=404, detail=f"No ready '{tier}' output for this project yet")

    # Idempotency key is scoped to (project, tier) rather than per-request --
    # a repeat download of a tier you've already paid for is a free
    # re-download (and, once built, a free full-site download too), not a
    # second charge, same ledger-idempotency pattern used for
    # signup_grant/generation_spend.
    try:
        wallet_service.spend(
            db,
            user_id=project.user_id,
            amount=tier_info.download_credit_cost,
            reason="download_spend",
            related_project_id=project.id,
            related_job_id=preview_job.id,
            idempotency_key=wallet_service.download_spend_key(project.id, tier),
        )
    except InsufficientCreditsError as exc:
        db.rollback()
        balance = wallet_service.get_or_create_wallet(db, project.user_id).balance
        db.commit()
        required = tier_info.download_credit_cost
        # Structured so the frontend can offer an exact top-up
        # (/checkout?credits=<shortfall>) instead of a generic failure.
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Insufficient credits for this download",
                "required": required,
                "balance": balance,
                "shortfall": max(required - balance, 0),
            },
        ) from exc
    db.commit()

    # Race guard: two near-simultaneous download clicks for the same
    # (project, tier) could otherwise both pass the "no full-site job
    # running yet" check below before either commits its new GenerationJob
    # row, launching duplicate full-site builds -- wallet_service.spend's
    # row lock (above) only protects the charge, not this check-then-create
    # sequence. Locking the Project row here (same SELECT ... FOR UPDATE
    # style wallet_service.spend/queue.claim_next_job already use in this
    # codebase) makes a second concurrent request block until the first
    # request's transaction commits its new job row, then re-read the
    # now-current state instead of racing past it.
    db.query(Project).filter(Project.id == project.id).with_for_update().one()

    page_count = _latest_page_count(db, project.id)
    full_site_job = _latest_full_site_job(db, project.id, tier)
    plan = _resolve_download_plan(page_count, full_site_job)

    if plan == "fast_path":
        return DownloadStartResponse(status="ready", project_id=project_id, tier=tier)
    if plan == "already_building":
        return DownloadStartResponse(
            status="building", project_id=project_id, tier=tier, job_id=str(full_site_job.id)
        )

    # plan == "start_build"
    new_job = GenerationJob(
        project_id=project.id,
        blueprint_id=preview_job.blueprint_id,
        tier=tier,
        overall_status="running",
        scope="full_site",
    )
    db.add(new_job)
    db.flush()
    enqueue(db, "generate_full_site", {"project_id": project_id, "tier": tier, "job_id": str(new_job.id)})
    db.commit()
    return DownloadStartResponse(status="building", project_id=project_id, tier=tier, job_id=str(new_job.id))


@router.get("/projects/{project_id}/download-status", response_model=DownloadStatusResponse)
def get_download_status(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadStatusResponse:
    project = _get_owned_project(db, project_id, current_user)

    tier_info = tier_service.get_tier(tier)
    if tier_info is None or not tier_info.is_active:
        raise HTTPException(status_code=400, detail=f"Unknown or disabled tier '{tier}'")

    page_count = _latest_page_count(db, project.id)
    full_site_job = _latest_full_site_job(db, project.id, tier)
    plan = _resolve_download_plan(page_count, full_site_job)

    if plan == "fast_path":
        return DownloadStatusResponse(status="ready")
    if plan == "already_building":
        return DownloadStatusResponse(status="building")
    # plan == "start_build" here only means "no build exists yet" (this
    # endpoint never starts one) or "the last attempt failed" -- surface
    # the failure reason in the latter case so the frontend can show it.
    if full_site_job is not None and full_site_job.overall_status == "failed":
        return DownloadStatusResponse(status="failed", failure_reason=full_site_job.failure_reason)
    return DownloadStatusResponse(status="ready")


@router.get("/projects/{project_id}/download-file")
def download_file(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    project = _get_owned_project(db, project_id, current_user)

    tier_info = tier_service.get_tier(tier)
    if tier_info is None or not tier_info.is_active:
        raise HTTPException(status_code=400, detail=f"Unknown or disabled tier '{tier}'")

    full_site_job = _latest_full_site_job(db, project.id, tier)
    if full_site_job is not None and full_site_job.overall_status == "succeeded" and full_site_job.output:
        output = full_site_job.output
    else:
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
            raise HTTPException(status_code=404, detail=f"No ready '{tier}' output for this project yet")
        output = preview_job.output

    # No charge here -- already charged (idempotently) in start_download.
    archive_path = build_download_zip(project_id, tier, output.output_storage_path)
    return FileResponse(
        archive_path, media_type="application/zip", filename=f"{project_id}-{tier}.zip"
    )
