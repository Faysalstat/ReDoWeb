import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas.admin.projects import (
    AdminBlueprintSummary,
    AdminGenerationJobSummary,
    AdminGenerationOutputSummary,
    AdminProjectDetailResponse,
    AdminProjectListItem,
    AdminProjectListResponse,
)
from ...services import admin_analytics_service

router = APIRouter()


@router.get("/projects", response_model=AdminProjectListResponse)
def list_projects(
    status: str | None = None,
    tier: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminProjectListResponse:
    result = admin_analytics_service.list_projects(
        db, status=status, tier=tier, search=search, page=page, page_size=page_size
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
            )
            for item in result.items
        ],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/{project_id}", response_model=AdminProjectDetailResponse)
def get_project_detail(project_id: str, db: Session = Depends(get_db)) -> AdminProjectDetailResponse:
    result = admin_analytics_service.get_project_detail(db, uuid.UUID(project_id))
    if result is None:
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")
    project, owner, blueprint, jobs = result

    blueprint_summary = None
    if blueprint is not None:
        blueprint_summary = AdminBlueprintSummary(
            site_name=blueprint.site_name,
            colors=blueprint.colors,
            fonts=blueprint.fonts,
            tone=blueprint.tone,
            version=blueprint.version,
        )

    job_summaries = [
        AdminGenerationJobSummary(
            job_id=str(job.id),
            tier=job.tier,
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
                )
                if job.output is not None
                else None
            ),
        )
        for job in jobs
    ]

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
    )
