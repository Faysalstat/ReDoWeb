"""Admin soft delete of a project.

Removes every file the project has on disk (crawl, blueprint, all tier
output incl. purchased designs, cached ZIPs) to free space immediately, but
keeps the Project row and all its history -- generation jobs, token usage /
costs, credit ledger, purchases, submission log (needed for abuse/DMCA
response). The row is stamped deleted_at / deleted_by_admin_id /
deletion_reason, and every owner-facing route then answers 404.

No automatic refund, even when designs were purchased (user decision
2026-10-06) -- the admin panel warns, and an admin can refund through the
existing credit adjustment on the user's page.
"""

import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Project
from .storage_cleanup_service import (
    RUNNING_JOB_GRACE,
    SETTLED_STATUSES,
    dir_size,
    has_recent_running_job,
)

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    pass


class ProjectAlreadyDeletedError(Exception):
    pass


class ProjectBusyError(Exception):
    """A pipeline stage or post-purchase job may still be writing files."""


@dataclass
class DeletionResult:
    project_id: uuid.UUID
    deleted_at: datetime
    bytes_freed: int


def is_project_busy(status: str, updated_at: datetime, has_recent_running_job: bool, now: datetime) -> bool:
    """Pure: refuse to delete while something may still be writing into the
    project folder. A project stuck mid-pipeline with no activity for a day
    is a dead pipeline and may be deleted."""
    if has_recent_running_job:
        return True
    return status not in SETTLED_STATUSES and updated_at > now - RUNNING_JOB_GRACE


def soft_delete_project(
    db: Session,
    project_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str | None = None,
    now: datetime | None = None,
) -> DeletionResult:
    now = now or datetime.now(timezone.utc)
    # Same row lock as Buy and the retention cleanup, so neither can run
    # against this project halfway through a delete.
    project = (
        db.query(Project).filter(Project.id == project_id).with_for_update().populate_existing().one_or_none()
    )
    if project is None:
        raise ProjectNotFoundError(str(project_id))

    project_root = Path(get_settings().storage_root) / "projects" / str(project.id)

    if project.deleted_at is not None:
        if not project_root.exists():
            db.rollback()
            raise ProjectAlreadyDeletedError(str(project_id))
        # Marked deleted but files still there (a previous delete's file
        # removal failed) -- finish it; keep the original stamp.
    else:
        if is_project_busy(project.status, project.updated_at, has_recent_running_job(db, project.id, now), now):
            db.rollback()
            raise ProjectBusyError(str(project_id))
        project.deleted_at = now
        project.deleted_by_admin_id = admin_id
        project.deletion_reason = (reason or "").strip() or None
        project.pending_tier_keys = None

    # Mark first, then remove files: if removal fails half-way the project is
    # already hidden from its owner, and calling delete again finishes it.
    deleted_at = project.deleted_at
    db.commit()

    bytes_freed = 0
    if project_root.is_dir():
        bytes_freed = dir_size(project_root)
        shutil.rmtree(project_root)

    logger.info(
        "admin %s deleted project %s (freed %.1f MB)%s",
        admin_id,
        project_id,
        bytes_freed / 1024**2,
        f": {reason}" if reason else "",
        extra={"event": "admin.project_deleted", "project_id": str(project_id)},
    )
    return DeletionResult(project_id=project.id, deleted_at=deleted_at, bytes_freed=bytes_freed)
