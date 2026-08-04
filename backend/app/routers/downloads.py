import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..db.session import get_db
from ..models import GenerationJob, Project, User
from ..services import tier_service, wallet_service
from ..services.download_service import build_download_zip
from ..services.wallet_service import InsufficientCreditsError

router = APIRouter(prefix="/api/v1", tags=["downloads"])


@router.post("/projects/{project_id}/download")
def download_project(
    project_id: str,
    tier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    project = db.get(Project, uuid.UUID(project_id))
    if project is None or project.user_id != current_user.id:
        # Same 404 for "doesn't exist" and "not yours" as GET /projects/{id}.
        raise HTTPException(status_code=404, detail=f"No project found for id {project_id}")

    tier_info = tier_service.get_tier(tier)
    if tier_info is None or not tier_info.is_active:
        raise HTTPException(status_code=400, detail=f"Unknown or disabled tier '{tier}'")

    job = (
        db.query(GenerationJob)
        .filter(
            GenerationJob.project_id == project.id,
            GenerationJob.tier == tier,
            GenerationJob.overall_status == "succeeded",
        )
        .order_by(GenerationJob.created_at.desc())
        .first()
    )
    if job is None or job.output is None:
        raise HTTPException(status_code=404, detail=f"No ready '{tier}' output for this project yet")

    # Idempotency key is scoped to (project, tier) rather than per-request --
    # a repeat download of a tier you've already paid for is a free
    # re-download, not a second charge, same ledger-idempotency pattern used
    # for signup_grant/generation_spend.
    try:
        wallet_service.spend(
            db,
            user_id=project.user_id,
            amount=tier_info.download_credit_cost,
            reason="download_spend",
            related_project_id=project.id,
            related_job_id=job.id,
            idempotency_key=f"download_spend:{project.id}:{tier}",
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail="Insufficient credits for this download") from exc
    db.commit()

    archive_path = build_download_zip(project_id, tier, job.output.output_storage_path)
    return FileResponse(
        archive_path, media_type="application/zip", filename=f"{project_id}-{tier}.zip"
    )
