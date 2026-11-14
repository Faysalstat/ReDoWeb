import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as StarletteUploadFile

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..db.session import get_db
from ..models import Blueprint, GenerationJob, Project, SubmissionLog, User
from ..rate_limit import limiter
from ..schemas.crawl import CrawlRequest
from ..schemas.project import (
    GenerationApprovalResponse,
    GenerationCostGateInfo,
    ProjectBlueprintSummary,
    ProjectGenerationSummary,
    ProjectListItem,
    ProjectStatusResponse,
    ProjectSubmitResponse,
    ProjectTierActions,
    ProjectTierFailure,
    TierRetryResponse,
)
from ..services import (
    brand_assets_service,
    cost_estimation_service,
    cost_settings_service,
    generation_status_service,
    storage_capacity_service,
    tier_actions_service,
    tier_service,
    wallet_service,
)
from ..services.storage_capacity_service import InsufficientDiskSpaceError
from ..workers.queue import enqueue

router = APIRouter(prefix="/api/v1", tags=["projects"])


def _outcome_status(outcomes: dict[str, generation_status_service.TierOutcome], tier_key: str) -> str | None:
    outcome = outcomes.get(tier_key)
    return outcome.status if outcome is not None else None


@router.post("/projects", response_model=ProjectSubmitResponse, status_code=202)
@limiter.limit(get_settings().rate_limit_submit)
def submit_project(
    payload: CrawlRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectSubmitResponse:
    return _create_project(db, request, current_user, payload)


def _form_bool(value) -> bool:
    return isinstance(value, str) and value.strip().lower() in ("1", "true", "on", "yes")


@router.post("/projects/with-brand-assets", response_model=ProjectSubmitResponse, status_code=202)
@limiter.limit(get_settings().rate_limit_submit)
async def submit_project_with_brand_assets(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectSubmitResponse:
    """Same as POST /projects, plus the logo / hero image from client-ng's
    pop-up (multipart: url, tos_accepted, brand_assets_later, logo?, hero?).
    Both files are required unless brand_assets_later is true; with it, each
    is optional (the crawled site's image is used instead).

    The form is parsed here, not through FastAPI params, so the size check
    below runs *before* the body is read -- FastAPI reads a multipart body
    before any dependency or handler code runs."""
    settings = get_settings()
    max_bytes = settings.brand_asset_max_bytes
    content_length = request.headers.get("content-length")
    if content_length is None or not content_length.isdigit():
        raise HTTPException(status_code=411, detail="Content-Length is required")
    if int(content_length) > 2 * max_bytes + 1024 * 1024:
        raise HTTPException(status_code=413, detail="The uploaded files are too large")

    form = await request.form(max_files=2, max_fields=10)
    try:
        try:
            payload = CrawlRequest(url=form.get("url") or "", tos_accepted=_form_bool(form.get("tos_accepted")))
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Please enter a valid website URL") from exc
        later = _form_bool(form.get("brand_assets_later"))

        uploads = {}
        for role in brand_assets_service.ROLES:
            upload = form.get(role)
            if isinstance(upload, StarletteUploadFile) and upload.filename:
                uploads[role] = await upload.read(max_bytes + 1)

        missing = brand_assets_service.missing_roles("logo" in uploads, "hero" in uploads, later)
        if missing:
            labels = " and ".join("a logo" if role == "logo" else "a hero image" for role in missing)
            raise HTTPException(
                status_code=422,
                detail=f"Please upload {labels}, or tick \"I'll change them later\".",
            )

        def _process_all() -> list[brand_assets_service.ProcessedImage]:
            return [
                brand_assets_service.process_image_bytes(
                    data,
                    role,
                    max_bytes=max_bytes,
                    max_side=settings.brand_logo_max_side_px if role == "logo" else settings.brand_hero_max_side_px,
                )
                for role, data in uploads.items()
            ]

        try:
            images = await run_in_threadpool(_process_all)
        except brand_assets_service.BrandAssetError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await form.close()

    def _attach_brand_assets(project: Project) -> None:
        project_root = Path(settings.storage_root) / "projects" / str(project.id)
        project.brand_assets_later = later
        for image in images:
            path = brand_assets_service.save(project_root, image)
            if image.role == "logo":
                project.brand_logo_path = path
            else:
                project.brand_hero_path = path

    return await run_in_threadpool(
        _create_project, db, request, current_user, payload, _attach_brand_assets
    )


def _create_project(
    db: Session,
    request: Request,
    current_user: User,
    payload: CrawlRequest,
    before_commit: Callable[[Project], None] | None = None,
) -> ProjectSubmitResponse:
    """Shared by both submit routes. `before_commit` runs after the project
    row is flushed (so it has an id) and before anything is committed or
    enqueued; if it raises, the row is rolled back, any brand_assets/ it wrote
    is removed, and no crawl is enqueued."""
    client_ip = request.client.host if request.client else None

    # Checked before any DB writes or credit check -- a rejected submission
    # here never charges a credit and never enqueues a crawl.
    try:
        storage_capacity_service.check_free_disk_space()
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Fast-fail before spending any crawl/AI cost -- this is a UX
    # optimization only, not the real enforcement (that's the row-locking
    # spend() call in generate_tier_task once crawl+blueprint have actually
    # succeeded, which is what actually decides whether the charge happens).
    wallet = wallet_service.get_or_create_wallet(db, current_user.id)
    if wallet.balance < wallet_service.GENERATION_SPEND_CREDITS:
        raise HTTPException(status_code=402, detail="Insufficient credits to start a generation")

    project = Project(
        user_id=current_user.id,
        source_url=str(payload.url),
        tos_accepted=payload.tos_accepted,
        submitted_ip=client_ip,
        status="pending",
    )
    db.add(project)
    db.flush()

    db.add(
        SubmissionLog(
            project_id=project.id,
            user_id=current_user.id,
            url=str(payload.url),
            ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            tos_accepted=payload.tos_accepted,
        )
    )
    if before_commit is not None:
        try:
            before_commit(project)
        except Exception:
            db.rollback()
            brand_dir = (
                Path(get_settings().storage_root) / "projects" / str(project.id) / brand_assets_service.BRAND_ASSETS_DIR
            )
            shutil.rmtree(brand_dir, ignore_errors=True)
            try:
                brand_dir.parent.rmdir()  # only succeeds if nothing else is in it
            except OSError:
                pass
            raise
    db.commit()

    project_id = str(project.id)

    # Every enabled tier's generate_tier job is enqueued as an independent
    # fan-out (see tasks_blueprint.py::extract_blueprint_task) once crawl +
    # blueprint extraction succeed, rather than chained one at a time -- see
    # docs/concurrency-scaling-plan.md.
    tier_keys = [tier.key for tier in tier_service.get_enabled_tiers()]
    enqueue(db, "run_crawl", {"project_id": project_id, "url": str(payload.url), "tier_keys": tier_keys})
    db.commit()

    return ProjectSubmitResponse(project_id=project_id, status=project.status)


@router.get("/projects", response_model=list[ProjectListItem])
def list_projects(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[ProjectListItem]:
    projects = (
        db.query(Project)
        # Admin soft-deleted projects are hidden from their owner.
        .filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
        .all()
    )

    # Most recent GenerationJob.tier per project, for the list's tier badge.
    # None while a project is still crawling/extracting (no job started yet).
    jobs = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id.in_([p.id for p in projects]))
        .order_by(GenerationJob.created_at.desc())
        .all()
    )
    latest_tier_by_project: dict[uuid.UUID, str] = {}
    for job in jobs:
        latest_tier_by_project.setdefault(job.project_id, job.tier)
    purchased = wallet_service.purchased_download_tiers(db, current_user.id, [p.id for p in projects])

    return [
        ProjectListItem(
            project_id=str(p.id),
            source_url=p.source_url,
            status=p.status,
            created_at=p.created_at,
            tier=latest_tier_by_project.get(p.id),
            purchased_tiers=purchased.get(p.id, []),
            previews_expired=p.previews_expired_at is not None,
        )
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=ProjectStatusResponse)
def get_project_status(
    project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectStatusResponse:
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or project.user_id != current_user.id or project.deleted_at is not None:
        # Same 404 for "doesn't exist" and "not yours" -- don't leak existence
        # of other users' projects.
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")

    blueprint_summary = None
    blueprint_row = (
        db.query(Blueprint)
        .filter(Blueprint.project_id == project.id, Blueprint.is_current.is_(True))
        .one_or_none()
    )
    if blueprint_row is not None:
        blueprint_summary = ProjectBlueprintSummary(
            site_name=blueprint_row.site_name,
            colors=blueprint_row.colors,
            fonts=blueprint_row.fonts,
            tone=blueprint_row.tone,
        )

    # All enabled tiers' generate_tier jobs are enqueued as an independent
    # fan-out (see submit_project above), so several GenerationJob rows can
    # exist for one project at once, potentially more than one "running"
    # concurrently on different queue workers. Surface every succeeded
    # tier's output as soon as it lands, ordered to match the enabled-tiers
    # display order, rather than waiting for the whole project to reach
    # "ready".
    enabled_tiers = tier_service.get_enabled_tiers()
    tier_order = {tier.key: index for index, tier in enumerate(enabled_tiers)}

    # Preview scope only, newest first: a full_site job (tasks_full_site.py)
    # builds into a sibling directory for the same tier and must not show up
    # as a second preview tab, and a retry's newer job supersedes the failed
    # attempt it replaced.
    jobs = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project.id, GenerationJob.scope == "preview")
        .order_by(GenerationJob.created_at.desc())
        .all()
    )
    generations: list[ProjectGenerationSummary] = []
    seen_tiers: set[str] = set()
    for job in jobs:
        if job.tier in seen_tiers or job.overall_status != "succeeded" or job.output is None:
            continue
        seen_tiers.add(job.tier)
        generations.append(
            ProjectGenerationSummary(
                tier=job.tier,
                template_used=job.output.template_used,
                preview_url_path=job.output.preview_url_path,
                summary=job.output.summary,
                contrast_warnings=job.output.contrast_warnings or [],
            )
        )
    generations.sort(key=lambda gen: tier_order.get(gen.tier, len(tier_order)))

    purchased_tiers = wallet_service.purchased_download_tiers(db, current_user.id, [project.id]).get(
        project.id, []
    )
    previews_expired = project.previews_expired_at is not None
    if previews_expired:
        # storage_cleanup_service deleted every unpurchased tier's files --
        # only purchased designs are still on disk to show.
        generations = [gen for gen in generations if gen.tier in purchased_tiers]

    # A tier that failed is reported on its own rather than failing the whole
    # project -- the tiers that did succeed stay previewable above, and each
    # failure is separately retryable (see retry_tier below) -- until the
    # project expires, after which a retry is no longer possible.
    outcomes = generation_status_service.get_preview_tier_outcomes(db, project.id)
    # Plural: fan-out means more than one tier can be "running" at once, not
    # just the tail of a chain -- see tier_service.get_enabled_tiers() usage
    # above and docs/concurrency-scaling-plan.md.
    current_tiers = [tier.key for tier in enabled_tiers if _outcome_status(outcomes, tier.key) == "running"]
    tier_failures = [
        ProjectTierFailure(tier=tier.key, failure_reason=outcomes[tier.key].failure_reason)
        for tier in enabled_tiers
        if _outcome_status(outcomes, tier.key) == "failed" and not previews_expired
    ]

    cost_gate = None
    if project.status == "awaiting_cost_approval":
        wallet = wallet_service.get_or_create_wallet(db, current_user.id)
        usd_per_credit = cost_settings_service.get_usd_per_credit(db)
        gate_info = cost_estimation_service.compute_cost_gate_info(
            project.estimated_generation_cost_usd, wallet.balance, usd_per_credit
        )
        cost_gate = GenerationCostGateInfo(**gate_info.__dict__)

    return ProjectStatusResponse(
        project_id=project_id,
        status=project.status,
        rejection_reason=project.rejection_reason,
        source_url=project.source_url,
        blueprint=blueprint_summary,
        generations=generations,
        tiers_total=len(enabled_tiers),
        tiers_completed=len(generations),
        current_tiers=current_tiers,
        tier_failures=tier_failures,
        cost_gate=cost_gate,
        purchased_tiers=purchased_tiers,
        previews_expired=previews_expired,
        previews_expired_at=project.previews_expired_at,
        page_count=tier_actions_service.latest_page_count(db, project.id),
        tier_actions={
            tier: ProjectTierActions(**actions.__dict__)
            for tier, actions in tier_actions_service.tier_actions(
                db, project, [gen.tier for gen in generations]
            ).items()
        },
    )


@router.post("/projects/{project_id}/approve-generation", response_model=GenerationApprovalResponse)
def approve_generation(
    project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> GenerationApprovalResponse:
    """User's response to the awaiting_cost_approval gate set by
    tasks_blueprint.py (see docs/generation-cost-gate-plan.md). A 200 with
    approved=False on insufficient balance is a normal, poll-able outcome,
    not a fault -- no debit happens here either way. The existing flat
    wallet_service.spend() inside generate_tier_task remains the sole,
    authoritative, row-locked charge, unchanged; this is purely a
    balance-sufficiency pre-check against the estimate."""
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or project.user_id != current_user.id or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")
    if project.status != "awaiting_cost_approval":
        raise HTTPException(status_code=409, detail="No pending generation approval for this project")

    wallet = wallet_service.get_or_create_wallet(db, current_user.id)
    usd_per_credit = cost_settings_service.get_usd_per_credit(db)
    gate_info = cost_estimation_service.compute_cost_gate_info(
        project.estimated_generation_cost_usd, wallet.balance, usd_per_credit
    )

    if gate_info.shortfall_credits > 0:
        return GenerationApprovalResponse(
            project_id=project_id, status=project.status, approved=False, **gate_info.__dict__
        )

    for tier_key in project.pending_tier_keys:
        enqueue(db, "generate_tier", {"project_id": project_id, "tier": tier_key})
    project.status = "blueprint_ready"
    project.pending_tier_keys = None
    db.commit()

    return GenerationApprovalResponse(
        project_id=project_id, status=project.status, approved=True, **gate_info.__dict__
    )


@router.post("/projects/{project_id}/retry-tier", response_model=TierRetryResponse)
def retry_tier(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TierRetryResponse:
    """Re-runs one failed tier's generation against the blueprint already on
    disk -- no re-crawl, no re-review, and no extra credits (the project's
    `generation_spend` idempotency key was already spent on the first
    attempt, so generate_tier_task's spend() call no-ops on the retry).

    Only a tier whose *latest* preview job failed can be retried; a tier
    that's still running, or that already succeeded, is a 409.
    """
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or project.user_id != current_user.id or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")
    if not tier_service.is_tier_enabled(tier, db):
        raise HTTPException(status_code=404, detail=f"No enabled tier named {tier!r}")

    if project.previews_expired_at is not None:
        # The crawl snapshot the retry would copy images from is gone.
        raise HTTPException(status_code=410, detail="This project has expired -- submit the site again")

    outcomes = generation_status_service.get_preview_tier_outcomes(db, project.id)
    if _outcome_status(outcomes, tier) != "failed":
        raise HTTPException(status_code=409, detail=f"Tier {tier!r} has no failed generation to retry")

    enqueue(db, "generate_tier", {"project_id": project_id, "tier": tier})
    project.status = "generating"
    project.rejection_reason = None
    db.commit()

    return TierRetryResponse(project_id=project_id, tier=tier, status=project.status)
