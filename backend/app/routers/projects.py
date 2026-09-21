import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..db.session import get_db
from ..models import Blueprint, GenerationJob, Project, SubmissionLog, User
from ..rate_limit import limiter
from ..schemas.crawl import CrawlRequest
from ..schemas.project import (
    ProjectBlueprintSummary,
    ProjectGenerationSummary,
    ProjectListItem,
    ProjectStatusResponse,
    ProjectSubmitResponse,
)
from ..services import storage_capacity_service, tier_service, wallet_service
from ..services.storage_capacity_service import InsufficientDiskSpaceError
from ..workers.queue import enqueue

router = APIRouter(prefix="/api/v1", tags=["projects"])


@router.post("/projects", response_model=ProjectSubmitResponse, status_code=202)
@limiter.limit(get_settings().rate_limit_submit)
def submit_project(
    payload: CrawlRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectSubmitResponse:
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
        .filter(Project.user_id == current_user.id)
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

    return [
        ProjectListItem(
            project_id=str(p.id),
            source_url=p.source_url,
            status=p.status,
            created_at=p.created_at,
            tier=latest_tier_by_project.get(p.id),
        )
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=ProjectStatusResponse)
def get_project_status(
    project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProjectStatusResponse:
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or project.user_id != current_user.id:
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

    jobs = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project.id)
        .order_by(GenerationJob.created_at)
        .all()
    )
    generations = [
        ProjectGenerationSummary(
            tier=job.tier,
            template_used=job.output.template_used,
            preview_url_path=job.output.preview_url_path,
            summary=job.output.summary,
            contrast_warnings=job.output.contrast_warnings or [],
        )
        for job in jobs
        if job.overall_status == "succeeded" and job.output is not None
    ]
    generations.sort(key=lambda gen: tier_order.get(gen.tier, len(tier_order)))
    # Plural: fan-out means more than one tier can be "running" at once, not
    # just the tail of a chain -- see tier_service.get_enabled_tiers() usage
    # above and docs/concurrency-scaling-plan.md.
    current_tiers = [job.tier for job in jobs if job.overall_status == "running"]

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
    )
