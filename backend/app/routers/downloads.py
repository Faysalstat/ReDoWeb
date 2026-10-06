"""Buy a tier's design, then the three post-purchase actions it unlocks:
Download ZIP, Generate all pages, Run SEO agent (Pro/Premium). See
docs/seo-agent-and-buy-flow-plan.md.

Buying is the only charge (download_spend, idempotent per project+tier --
the same ledger key purchases have always used, so every earlier purchase
still counts). Every post-purchase endpoint checks that purchase and
answers 403 without it -- previously GET /download-file served the ZIP to
the project owner without checking payment at all."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..db.session import get_db
from ..models import GenerationJob, Project, User
from ..schemas.download import ActionStartResponse, DownloadStartResponse, PurchaseResponse
from ..services import tier_actions_service, tier_service, wallet_service
from ..services.download_service import build_download_zip
from ..services.wallet_service import InsufficientCreditsError
from ..workers.queue import enqueue

router = APIRouter(prefix="/api/v1", tags=["downloads"])

NOT_PURCHASED_DETAIL = "Buy this design first"


def _get_owned_project(db: Session, project_id: str, current_user: User) -> Project:
    try:
        project = db.get(Project, uuid.UUID(project_id))
    except ValueError:
        project = None
    if project is None or project.user_id != current_user.id:
        # Same 404 for "doesn't exist" and "not yours" as GET /projects/{id}.
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")
    return project


def _require_active_tier(tier: str):
    tier_info = tier_service.get_tier(tier)
    if tier_info is None or not tier_info.is_active:
        raise HTTPException(status_code=400, detail=f"Unknown or disabled tier '{tier}'")
    return tier_info


def _succeeded_preview_job(db: Session, project: Project, tier: str) -> GenerationJob:
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
    return preview_job


def _require_purchased(db: Session, project: Project, tier: str) -> None:
    if not tier_actions_service.is_purchased(db, project, tier):
        raise HTTPException(status_code=403, detail=NOT_PURCHASED_DETAIL)


def _lock_project(db: Session, project: Project) -> None:
    """Race guard: two near-simultaneous clicks for the same (project, tier)
    could otherwise both pass the "nothing running yet" check before
    either commits its new GenerationJob row, launching duplicate builds.
    Locking the Project row (same SELECT ... FOR UPDATE style
    wallet_service.spend / queue.claim_next_job use) makes the second
    request wait for the first to commit, then re-read the current state."""
    db.query(Project).filter(Project.id == project.id).with_for_update().one()


def _purchase(db: Session, project: Project, tier: str) -> None:
    tier_info = _require_active_tier(tier)
    preview_job = _succeeded_preview_job(db, project, tier)
    # Idempotency key is scoped to (project, tier), not per request -- buying
    # an already-bought tier costs nothing.
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
                "message": "Insufficient credits to buy this design",
                "required": required,
                "balance": balance,
                "shortfall": max(required - balance, 0),
            },
        ) from exc
    db.commit()


@router.post("/projects/{project_id}/purchase", response_model=PurchaseResponse)
def purchase_tier(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseResponse:
    """Buy a tier's design. Unlocks Download ZIP, Generate all pages and
    (Pro/Premium) Run SEO agent. Starts nothing by itself."""
    project = _get_owned_project(db, project_id, current_user)
    _purchase(db, project, tier)
    return PurchaseResponse(purchased=True, project_id=project_id, tier=tier)


@router.post("/projects/{project_id}/download", response_model=DownloadStartResponse, deprecated=True)
def start_download(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadStartResponse:
    """Deprecated alias for POST /purchase, kept so a browser tab still
    running the pre-Buy-split frontend keeps working after deploy. Never
    auto-starts a full-site build any more."""
    project = _get_owned_project(db, project_id, current_user)
    _purchase(db, project, tier)
    return DownloadStartResponse(status="ready", project_id=project_id, tier=tier)


@router.post("/projects/{project_id}/full-site", response_model=ActionStartResponse)
def start_full_site(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionStartResponse:
    """Generate all pages: builds the rest of a multi-page site from the
    saved blueprint in the preview's exact design (tasks_full_site). Once
    per purchase; a retry is allowed only after a failure."""
    project = _get_owned_project(db, project_id, current_user)
    _require_active_tier(tier)
    _require_purchased(db, project, tier)
    preview_job = _succeeded_preview_job(db, project, tier)

    _lock_project(db, project)
    page_count = tier_actions_service.latest_page_count(db, project.id)
    full_site_job = tier_actions_service.latest_job(db, project.id, tier, "full_site")
    action = tier_actions_service.resolve_full_site_action(page_count, full_site_job)

    if action == "not_applicable":
        raise HTTPException(status_code=400, detail="This site has only one page -- it's already complete")
    if action == "already_done":
        raise HTTPException(status_code=409, detail="All pages have already been generated for this design")
    if action == "running":
        db.commit()
        return ActionStartResponse(status="running", project_id=project_id, tier=tier, job_id=str(full_site_job.id))

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
    return ActionStartResponse(status="running", project_id=project_id, tier=tier, job_id=str(new_job.id))


@router.post("/projects/{project_id}/seo", response_model=ActionStartResponse)
def start_seo(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionStartResponse:
    """Run SEO agent (Pro/Premium): optimizes a copy of the finished site
    (tasks_seo). On a multi-page site it requires "Generate all pages" to
    have succeeded first. Once per purchase; retry only after a failure."""
    project = _get_owned_project(db, project_id, current_user)
    _require_active_tier(tier)
    _require_purchased(db, project, tier)
    preview_job = _succeeded_preview_job(db, project, tier)

    _lock_project(db, project)
    page_count = tier_actions_service.latest_page_count(db, project.id)
    full_site_job = tier_actions_service.latest_job(db, project.id, tier, "full_site")
    seo_job = tier_actions_service.latest_job(db, project.id, tier, "seo")
    action = tier_actions_service.resolve_seo_action(tier, page_count, full_site_job, seo_job)

    if action == "unavailable":
        raise HTTPException(status_code=400, detail="SEO optimization is available on Pro and Premium designs")
    if action == "needs_full_site":
        raise HTTPException(status_code=409, detail="Generate all pages first")
    if action == "already_done":
        raise HTTPException(status_code=409, detail="This design is already SEO optimized")
    if action == "running":
        db.commit()
        return ActionStartResponse(status="running", project_id=project_id, tier=tier, job_id=str(seo_job.id))

    new_job = GenerationJob(
        project_id=project.id,
        blueprint_id=preview_job.blueprint_id,
        tier=tier,
        overall_status="running",
        scope="seo",
    )
    db.add(new_job)
    db.flush()
    enqueue(db, "run_seo", {"project_id": project_id, "tier": tier, "job_id": str(new_job.id)})
    db.commit()
    return ActionStartResponse(status="running", project_id=project_id, tier=tier, job_id=str(new_job.id))


@router.get("/projects/{project_id}/download-file")
def download_file(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """The best finished output right now -- SEO version, then all pages,
    then the home-page preview. Purchase required."""
    project = _get_owned_project(db, project_id, current_user)
    _require_active_tier(tier)
    _require_purchased(db, project, tier)

    output = tier_actions_service.choose_download_scope(
        tier_actions_service.latest_succeeded_output(db, project.id, tier, "seo"),
        tier_actions_service.latest_succeeded_output(db, project.id, tier, "full_site"),
        tier_actions_service.latest_succeeded_output(db, project.id, tier, "preview"),
    )
    if output is None:
        raise HTTPException(status_code=404, detail=f"No ready '{tier}' output for this project yet")

    # No charge here -- the purchase already happened (POST /purchase).
    archive_path = build_download_zip(project_id, tier, output.output_storage_path)
    return FileResponse(
        archive_path, media_type="application/zip", filename=f"{project_id}-{tier}.zip"
    )
