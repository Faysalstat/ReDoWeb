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
from ..config import get_settings
from ..observability import context as log_context
from .billing_reconcile import run_reconcile_once
from .queue import TRACE_KEY, claim_next_job
from .storage_cleanup import run_cleanup_once
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

logger = logging.getLogger("app.worker")


CLEANUP_FIRST_RUN_DELAY_SECONDS = 300.0


def _maybe_run_storage_cleanup(next_run_at: float) -> float:
    """Runs the disk-retention cleanup when due (only between jobs, never
    while one is in flight); returns when it's next due. A failure is
    logged and retried next interval -- it must never kill the worker."""
    if time.monotonic() < next_run_at:
        return next_run_at
    interval = get_settings().storage_cleanup_interval_hours * 3600
    try:
        run_cleanup_once()
    except Exception:
        logger.exception("storage cleanup failed")
    return time.monotonic() + interval


# Short first delay: a purchase stranded while the worker was down should
# be picked up soon after a restart, not an interval later.
RECONCILE_FIRST_RUN_DELAY_SECONDS = 60.0


def _maybe_run_billing_reconcile(next_run_at: float) -> float:
    """Re-checks stale pending PayPal purchases with PayPal when due (see
    workers/billing_reconcile.py). Same between-jobs, never-kills-the-worker
    contract as the storage cleanup."""
    if time.monotonic() < next_run_at:
        return next_run_at
    interval = get_settings().billing_reconcile_interval_minutes * 60
    try:
        run_reconcile_once()
    except Exception:
        logger.exception("billing reconcile failed", extra={"event": "billing.reconcile_failed"})
    return time.monotonic() + interval


def run_worker_loop() -> None:
    logger.info("started, polling queued_jobs every %ss", POLL_INTERVAL_SECONDS, extra={"event": "worker.started"})
    next_cleanup_at = time.monotonic() + CLEANUP_FIRST_RUN_DELAY_SECONDS
    next_reconcile_at = time.monotonic() + RECONCILE_FIRST_RUN_DELAY_SECONDS
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
                job_id, task_name, payload = job.id, job.task_name, dict(job.payload)
                queued_at, started_at = job.created_at, job.started_at
        finally:
            db.close()

        if job is None:
            next_cleanup_at = _maybe_run_storage_cleanup(next_cleanup_at)
            next_reconcile_at = _maybe_run_billing_reconcile(next_reconcile_at)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        trace_id = payload.pop(TRACE_KEY, None) or log_context.new_trace_id()
        # Every line the task writes (and every job it enqueues) carries these.
        with log_context.scope(
            trace_id=trace_id,
            queued_job_id=job_id,
            task=task_name,
            project_id=payload.get("project_id"),
            tier=payload.get("tier"),
            job_id=payload.get("job_id"),
        ):
            _run_job(job_id, task_name, payload, queued_at, started_at)


def _run_job(job_id, task_name: str, payload: dict, queued_at: datetime, started_at: datetime) -> None:
    queue_wait_ms = round((started_at - queued_at).total_seconds() * 1000) if queued_at and started_at else None
    logger.info(
        "running %s (%s)", task_name, job_id, extra={"event": "job.started", "queue_wait_ms": queue_wait_ms}
    )
    clock = time.monotonic()

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
        logger.exception(
            "%s (%s) failed: %s",
            task_name,
            job_id,
            exc,
            extra={"event": "job.finished", "status": "failed", "duration_ms": _elapsed_ms(clock)},
        )
        return

    db = SessionLocal()
    try:
        row = db.get(QueuedJob, job_id)
        row.status = "succeeded"
        row.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
    logger.info(
        "%s (%s) succeeded",
        task_name,
        job_id,
        extra={"event": "job.finished", "status": "succeeded", "duration_ms": _elapsed_ms(clock)},
    )


def _elapsed_ms(clock: float) -> int:
    return round((time.monotonic() - clock) * 1000)


if __name__ == "__main__":
    configure_logging(service="worker", worker_id=WORKER_ID)
    run_worker_loop()
