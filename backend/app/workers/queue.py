from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import QueuedJob


def enqueue(db: Session, task_name: str, payload: dict) -> QueuedJob:
    """Adds a queued_jobs row to `db` without committing, so callers can
    enqueue the next pipeline stage in the same transaction as the current
    stage's terminal status update -- see queue_worker.py / CLAUDE.md."""
    job = QueuedJob(task_name=task_name, payload=payload, status="queued")
    db.add(job)
    return job


def claim_next_job(db: Session) -> QueuedJob | None:
    """Atomically claims the oldest queued row via SELECT ... FOR UPDATE
    SKIP LOCKED (same row-locking style as wallet_service.spend()) and
    commits the claim immediately, so a second worker process could run
    concurrently without double-claiming -- not needed today (one worker,
    matching the existing single-concurrency `--pool=solo` Celery setup),
    but the primitive is free."""
    job = db.scalars(
        select(QueuedJob)
        .where(QueuedJob.status == "queued")
        .order_by(QueuedJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).one_or_none()
    if job is None:
        return None

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    return job
