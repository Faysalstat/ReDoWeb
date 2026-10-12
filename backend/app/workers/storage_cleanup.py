"""Runs services/storage_cleanup_service.py -- on a timer from the queue
worker (queue_worker.py), or by hand:

    python -m app.workers.storage_cleanup --dry-run   # report only
    python -m app.workers.storage_cleanup             # actually delete

Runs inside the worker rather than as a separate cron service because on
Railway a volume attaches to one service only (see docs/RAILWAY.md).

A Postgres advisory lock makes concurrent runs (several queue workers, or a
manual run while a worker's timer fires) skip instead of doubling up."""

import argparse
import logging

from sqlalchemy import text

from ..db.session import SessionLocal, engine
from ..logging_config import configure_logging
from ..services.storage_cleanup_service import CleanupReport, run_storage_cleanup

logger = logging.getLogger(__name__)

# Arbitrary app-wide constant identifying this job's advisory lock.
CLEANUP_ADVISORY_LOCK_KEY = 0x52444F57  # "RDOW"


def run_cleanup_once(dry_run: bool = False) -> CleanupReport | None:
    """Returns the report, or None if another process holds the lock."""
    with engine.connect() as lock_conn:
        got_lock = lock_conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": CLEANUP_ADVISORY_LOCK_KEY}
        ).scalar()
        if not got_lock:
            logger.info("storage cleanup: another process is already running it, skipping")
            return None
        try:
            db = SessionLocal()
            try:
                report = run_storage_cleanup(db, dry_run=dry_run)
            finally:
                db.close()
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": CLEANUP_ADVISORY_LOCK_KEY})
            lock_conn.commit()

    logger.info(
        "storage cleanup%s: checked %d old projects, cleaned %d, %s %.1f MB, %d errors",
        " (dry run)" if dry_run else "",
        report.projects_checked,
        report.projects_cleaned,
        "would free" if dry_run else "freed",
        report.bytes_freed / 1024**2,
        len(report.errors),
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report what would be deleted, delete nothing")
    args = parser.parse_args()
    configure_logging(service="worker")
    run_cleanup_once(dry_run=args.dry_run)
