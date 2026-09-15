"""Postgres-backed replacement for `celery -A app.workers.celery_app worker`.
Run with: `python -m app.workers.queue_worker`. Single long-running process,
polling `queued_jobs` -- matches the previous Celery setup's concurrency
(Windows required `--pool=solo`, i.e. one task at a time), so there's no
concurrency loss from not sharding work across processes."""

import time
from datetime import datetime, timezone

from ..db.session import SessionLocal
from ..models import QueuedJob
from .queue import claim_next_job
from .tasks_blueprint import extract_blueprint_task
from .tasks_crawl import run_crawl_task
from .tasks_generate import generate_tier_task

POLL_INTERVAL_SECONDS = 1.0

TASK_HANDLERS = {
    "run_crawl": run_crawl_task,
    "extract_blueprint": extract_blueprint_task,
    "generate_tier": generate_tier_task,
}


def run_worker_loop() -> None:
    print("queue_worker: started, polling queued_jobs every " f"{POLL_INTERVAL_SECONDS}s")
    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db)
            # Read attributes while the session is still open -- commit()
            # expires them by default, so touching job.* after db.close()
            # below raises DetachedInstanceError and silently kills the
            # worker loop (no try/except wraps this section) before the
            # handler ever runs.
            if job is not None:
                job_id, task_name, payload = job.id, job.task_name, job.payload
        finally:
            db.close()

        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        print(f"queue_worker: running {task_name} ({job_id})")

        handler = TASK_HANDLERS[task_name]
        try:
            handler(**payload)
        except Exception as exc:
            # No auto-retry, matching the prior Celery setup's "no retry
            # policy" decision (CLAUDE.md) -- the handler itself already
            # left the Project row in a terminal failed/rejected state;
            # this just records the same outcome on the queue row so it's
            # visible without re-deriving it from Project.status.
            db = SessionLocal()
            try:
                row = db.get(QueuedJob, job_id)
                row.status = "failed"
                row.error = str(exc)
                row.finished_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()
            print(f"queue_worker: {task_name} ({job_id}) failed: {exc}")
            continue

        db = SessionLocal()
        try:
            row = db.get(QueuedJob, job_id)
            row.status = "succeeded"
            row.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
        print(f"queue_worker: {task_name} ({job_id}) succeeded")


if __name__ == "__main__":
    run_worker_loop()
