import uuid

from celery import chain
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
from ..services import tier_service, wallet_service
from ..workers.tasks_blueprint import extract_blueprint_task
from ..workers.tasks_crawl import run_crawl_task
from ..workers.tasks_generate import generate_tier_task

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

    # Only one tier is enabled today, so this is a simple linear chain. Once
    # basic/premium have real templates, the generate steps for each enabled
    # tier should become a Celery `group` (parallel) inserted at this point
    # instead of more chain links (sequential) -- see docs/PROGRESS.md.
    workflow = chain(run_crawl_task.s(project_id, str(payload.url)), extract_blueprint_task.s())
    for tier in tier_service.get_enabled_tiers():
        workflow |= generate_tier_task.s(tier.key)
    workflow.apply_async()

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

    generation_summary = None
    if project.status == "ready":
        job = (
            db.query(GenerationJob)
            .filter(GenerationJob.project_id == project.id, GenerationJob.overall_status == "succeeded")
            .order_by(GenerationJob.created_at.desc())
            .first()
        )
        if job is not None and job.output is not None:
            generation_summary = ProjectGenerationSummary(
                tier=job.tier,
                template_used=job.output.template_used,
                preview_url_path=job.output.preview_url_path,
                summary=job.output.summary,
                contrast_warnings=job.output.contrast_warnings or [],
            )

    return ProjectStatusResponse(
        project_id=project_id,
        status=project.status,
        rejection_reason=project.rejection_reason,
        source_url=project.source_url,
        blueprint=blueprint_summary,
        generation=generation_summary,
    )
