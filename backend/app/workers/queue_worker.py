"""Postgres-backed replacement for `celery -A app.workers.celery_app worker`.
Run with: `python -m app.workers.queue_worker`. Multiple instances of this
process can run concurrently against the same `queued_jobs` table -- claiming
is already safe via `claim_next_job()`'s `SELECT ... FOR UPDATE SKIP LOCKED`
(see queue.py) -- see docs/concurrency-scaling-plan.md for the recommended
worker count and rollout. A project's own pipeline stages can never race each
other regardless of worker count: stage N+1's queue row doesn't exist until
stage N's task creates it, so running more of this process only adds
parallelism *across* projects/tiers, never within one."""

import logging
import os
import time
import uuid
from datetime import datetime, timezone

from ..db.session import SessionLocal
from ..logging_config import configure_logging
from ..models import QueuedJob
from .queue import claim_next_job
from .tasks_blueprint import extract_blueprint_task
from .tasks_crawl import run_crawl_task
from .tasks_full_site import generate_full_site_task
from .tasks_generate import generate_tier_task
from .tasks_seo import run_seo_task

POLL_INTERVAL_SECONDS = 1.0

TASK_HANDLERS = {
    "run_crawl": run_crawl_task,
    "extract_blueprint": extract_blueprint_task,
    "generate_tier": generate_tier_task,
    "generate_full_site": generate_full_site_task,
    "run_seo": run_seo_task,
}

# Short per-process tag so concurrent workers' interleaved stdout is
# distinguishable -- falls back to a random suffix outside of
# start_workers.ps1 (which sets this per launched process).
WORKER_ID = os.environ.get("REDOWEBS_WORKER_ID") or uuid.uuid4().hex[:6]

logger = logging.getLogger(f"queue_worker[{WORKER_ID}]")


def run_worker_loop() -> None:
    logger.info("started, polling queued_jobs every %ss", POLL_INTERVAL_SECONDS)
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

        logger.info("running %s (%s)", task_name, job_id)

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
            # Every task re-raises after marking its own rows failed, so this
            # is the one place the original traceback is still available --
            # str(exc) alone (what queued_jobs.error stores) loses it.
            logger.exception("%s (%s) failed: %s", task_name, job_id, exc)
            continue

        db = SessionLocal()
        try:
            row = db.get(QueuedJob, job_id)
            row.status = "succeeded"
            row.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
        logger.info("%s (%s) succeeded", task_name, job_id)


if __name__ == "__main__":
    configure_logging()
    run_worker_loop()
