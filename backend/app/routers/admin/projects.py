import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import User
from ...schemas.admin.projects import (
    AdminBlueprintSummary,
    AdminDeleteProjectRequest,
    AdminDeleteProjectResponse,
    AdminGenerationJobSummary,
    AdminGenerationOutputSummary,
    AdminPaidTier,
    AdminProjectDetailResponse,
    AdminProjectListItem,
    AdminProjectListResponse,
)
from ...services import admin_analytics_service, project_deletion_service, wallet_service

router = APIRouter()


def _parse_project_id(project_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}") from None


@router.get("/projects", response_model=AdminProjectListResponse)
def list_projects(
    status: str | None = None,
    tier: str | None = None,
    search: str | None = None,
    user_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminProjectListResponse:
    result = admin_analytics_service.list_projects(
        db,
        status=status,
        tier=tier,
        search=search,
        user_id=uuid.UUID(user_id) if user_id else None,
        page=page,
        page_size=page_size,
    )
    return AdminProjectListResponse(
        items=[
            AdminProjectListItem(
                project_id=str(item.project_id),
                source_url=item.source_url,
                status=item.status,
                owner_email=item.owner_email,
                tier=item.tier,
                created_at=item.created_at,
                deleted_at=item.deleted_at,
            )
            for item in result.items
        ],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/{project_id}", response_model=AdminProjectDetailResponse)
def get_project_detail(project_id: str, db: Session = Depends(get_db)) -> AdminProjectDetailResponse:
    result = admin_analytics_service.get_project_detail(db, _parse_project_id(project_id))
    if result is None:
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")
    project, owner, blueprint, jobs, token_usage_by_job = result
    deleted_by = db.get(User, project.deleted_by_admin_id) if project.deleted_by_admin_id else None

    blueprint_summary = None
    if blueprint is not None:
        blueprint_summary = AdminBlueprintSummary(
            site_name=blueprint.site_name,
            colors=blueprint.colors,
            fonts=blueprint.fonts,
            tone=blueprint.tone,
            version=blueprint.version,
        )

    job_summaries = []
    for job in jobs:
        usage = token_usage_by_job.get(job.id)
        job_summaries.append(
            AdminGenerationJobSummary(
                job_id=str(job.id),
                tier=job.tier,
                scope=job.scope,
                overall_status=job.overall_status,
                failure_reason=job.failure_reason,
                created_at=job.created_at,
                finished_at=job.finished_at,
                output=(
                    AdminGenerationOutputSummary(
                        template_used=job.output.template_used,
                        preview_url_path=job.output.preview_url_path,
                        summary=job.output.summary,
                        contrast_warnings=job.output.contrast_warnings or [],
                        prompt_tokens=job.output.prompt_tokens,
                        completion_tokens=job.output.completion_tokens,
                        iterations=job.output.iterations,
                    )
                    if job.output is not None
                    else None
                ),
                models_used=usage.models_used if usage is not None else [],
                total_cost_usd=usage.total_cost_usd if usage is not None else 0.0,
                progress=job.progress,
            )
        )

    return AdminProjectDetailResponse(
        project_id=str(project.id),
        source_url=project.source_url,
        status=project.status,
        rejection_reason=project.rejection_reason,
        owner_email=owner.email,
        owner_id=str(owner.id),
        created_at=project.created_at,
        blueprint=blueprint_summary,
        generation_jobs=job_summaries,
        paid_tiers=[
            AdminPaidTier(tier=c.tier, credits=c.credits, charged_at=c.charged_at)
            for c in wallet_service.download_charges_for_project(db, project.id)
        ],
        deleted_at=project.deleted_at,
        deleted_by_email=deleted_by.email if deleted_by is not None else None,
        deletion_reason=project.deletion_reason,
        previews_expired_at=project.previews_expired_at,
    )


@router.post("/projects/{project_id}/delete", response_model=AdminDeleteProjectResponse)
def delete_project(
    project_id: str,
    body: AdminDeleteProjectRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminDeleteProjectResponse:
    """Soft delete: removes every file on disk (purchased designs too -- no
    automatic refund), keeps the project row and all its history, and hides
    it from the owner. See services/project_deletion_service.py."""
    try:
        result = project_deletion_service.soft_delete_project(
            db, _parse_project_id(project_id), admin_id=current_admin.id, reason=body.reason
        )
    except project_deletion_service.ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}") from None
    except project_deletion_service.ProjectAlreadyDeletedError:
        raise HTTPException(status_code=409, detail="This project is already deleted") from None
    except project_deletion_service.ProjectBusyError:
        raise HTTPException(
            status_code=409,
            detail="A job is still running for this project -- wait for it to finish, then delete",
        ) from None
    return AdminDeleteProjectResponse(
        project_id=str(result.project_id), deleted_at=result.deleted_at, bytes_freed=result.bytes_freed
    )
