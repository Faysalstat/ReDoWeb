"""Disk retention: frees the space old projects no longer need.

A project older than `storage_retention_days` (config.py) loses:
- every UNPURCHASED tier's preview (generated/{tier}/) -- it can no longer
  be bought or retried afterwards (routers check previews_expired_at);
- its crawl snapshot (snapshot/: page HTML + downloaded images) -- unless a
  purchased tier still needs it: "Generate all pages" copies its images from
  snapshot/, so a paid multi-page project keeps the crawl until every
  purchased tier's full-site build has succeeded;
- the cached download ZIPs (downloads/) -- rebuilt on every download anyway.

Never deleted: purchased tiers' output (preview, full/, seo/), blueprint/,
metadata.json (both tiny, and needed by full-site/SEO), and every DB row.

Why on the volume and not a separate cron service: Railway volumes attach to
one service only, so this runs inside the queue worker (see
workers/storage_cleanup.py), which shares the API's disk.

The decision functions (is_cleanup_due, plan_project_cleanup,
apply_cleanup_plan) are pure/filesystem-only so they're unit-testable --
Project has Postgres-only column types the SQLite test DB can't compile.
"""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import GenerationJob, Project
from . import tier_actions_service

logger = logging.getLogger(__name__)

# Statuses where no pipeline stage is pending. A project stuck in any other
# status is still cleaned once it has also been idle (updated_at) for the
# whole retention window -- that's a dead pipeline, not a running one.
SETTLED_STATUSES = {"ready", "failed", "rejected", "awaiting_cost_approval"}

# A GenerationJob marked "running" this recently might really be running
# (a retry or post-purchase action started just before the cutoff); older
# "running" rows are crashed jobs and don't block cleanup.
RUNNING_JOB_GRACE = timedelta(hours=24)

EXPIRED_APPROVAL_REASON = (
    "This project waited too long for cost approval and has expired. Submit the site again to start over."
)


@dataclass(frozen=True)
class CleanupPlan:
    tier_dirs_to_delete: tuple[str, ...]
    delete_snapshot: bool
    delete_downloads: bool = True


@dataclass
class CleanupReport:
    dry_run: bool
    retention_days: int
    projects_checked: int = 0
    projects_cleaned: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)


def is_cleanup_due(
    status: str,
    created_at: datetime,
    updated_at: datetime,
    cutoff: datetime,
    has_recent_running_job: bool,
) -> bool:
    if created_at >= cutoff or has_recent_running_job:
        return False
    return status in SETTLED_STATUSES or updated_at < cutoff


def plan_project_cleanup(
    tier_dirs_on_disk: set[str],
    purchased_tiers: set[str],
    page_count: int,
    full_site_succeeded_tiers: set[str],
) -> CleanupPlan:
    """Pure decision: what to delete for one past-retention project."""
    unpurchased = tuple(sorted(tier for tier in tier_dirs_on_disk if tier not in purchased_tiers))
    # A purchased tier on a multi-page site can still start "Generate all
    # pages" (or retry it after a failure), which copies images from
    # snapshot/ -- keep the crawl until none of them can.
    crawl_still_needed = page_count > 1 and any(
        tier not in full_site_succeeded_tiers for tier in purchased_tiers
    )
    return CleanupPlan(tier_dirs_to_delete=unpurchased, delete_snapshot=not crawl_still_needed)


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def apply_cleanup_plan(project_root: Path, plan: CleanupPlan, dry_run: bool = False) -> int:
    """Deletes what `plan` says under `project_root`; returns bytes freed
    (or that would be freed, for a dry run). Only ever touches the three
    known subpaths -- tier names come from directory listing, but are still
    resolved and checked to stay inside generated/."""
    generated_root = (project_root / "generated").resolve()
    targets: list[Path] = []
    for tier in plan.tier_dirs_to_delete:
        tier_dir = (generated_root / tier).resolve()
        if tier_dir.parent == generated_root:
            targets.append(tier_dir)
    if plan.delete_snapshot:
        targets.append(project_root / "snapshot")
    if plan.delete_downloads:
        targets.append(project_root / "downloads")

    freed = 0
    for target in targets:
        if not target.is_dir():
            continue
        size = dir_size(target)
        if not dry_run:
            shutil.rmtree(target)
        freed += size
    return freed


# --- DB plumbing -------------------------------------------------------------


def _lock_project(db: Session, project_id) -> Project:
    """Same row lock routers/downloads.py takes before a purchase, so a Buy
    click can't land between "not purchased" and the delete below -- the
    purchase either commits first (and is seen here) or waits and then sees
    previews_expired_at."""
    return (
        db.query(Project).filter(Project.id == project_id).with_for_update().populate_existing().one()
    )


def has_recent_running_job(db: Session, project_id, now: datetime) -> bool:
    return (
        db.query(GenerationJob.id)
        .filter(
            GenerationJob.project_id == project_id,
            GenerationJob.overall_status == "running",
            GenerationJob.created_at > now - RUNNING_JOB_GRACE,
        )
        .first()
        is not None
    )


def _full_site_succeeded_tiers(db: Session, project_id) -> set[str]:
    rows = (
        db.query(GenerationJob.tier)
        .filter(
            GenerationJob.project_id == project_id,
            GenerationJob.scope == "full_site",
            GenerationJob.overall_status == "succeeded",
        )
        .distinct()
        .all()
    )
    return {tier for (tier,) in rows}


def _cleanup_one(db: Session, project_id, storage_root: Path, now: datetime, cutoff: datetime, dry_run: bool) -> int | None:
    """Returns bytes freed, or None when the project wasn't due."""
    project = _lock_project(db, project_id)
    if not is_cleanup_due(
        project.status,
        project.created_at,
        project.updated_at,
        cutoff,
        has_recent_running_job(db, project.id, now),
    ):
        db.rollback()
        return None

    project_root = storage_root / "projects" / str(project.id)
    generated = project_root / "generated"
    tier_dirs = {p.name for p in generated.iterdir() if p.is_dir()} if generated.is_dir() else set()
    purchased = {tier for tier in tier_dirs if tier_actions_service.is_purchased(db, project, tier)}
    plan = plan_project_cleanup(
        tier_dirs_on_disk=tier_dirs,
        purchased_tiers=purchased,
        page_count=tier_actions_service.latest_page_count(db, project.id),
        full_site_succeeded_tiers=_full_site_succeeded_tiers(db, project.id),
    )
    freed = apply_cleanup_plan(project_root, plan, dry_run=dry_run)

    newly_expired = project.previews_expired_at is None
    if dry_run or (not newly_expired and freed == 0):
        db.rollback()
        return freed if newly_expired or freed else None

    if newly_expired:
        project.previews_expired_at = now
        if project.status == "awaiting_cost_approval":
            # Its snapshot is gone, so approving now would fail mid-generation.
            project.status = "failed"
            project.rejection_reason = EXPIRED_APPROVAL_REASON
            project.pending_tier_keys = None
    db.commit()
    logger.info(
        "storage cleanup: project %s -- removed tiers %s, snapshot=%s, freed %.1f MB",
        project.id,
        list(plan.tier_dirs_to_delete) or "none",
        plan.delete_snapshot,
        freed / 1024**2,
    )
    return freed


def run_storage_cleanup(db: Session, now: datetime | None = None, dry_run: bool = False) -> CleanupReport:
    settings = get_settings()
    report = CleanupReport(dry_run=dry_run, retention_days=settings.storage_retention_days)
    if settings.storage_retention_days <= 0:
        return report

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.storage_retention_days)
    storage_root = Path(settings.storage_root)

    # Already-expired projects are re-checked too: a paid multi-page project
    # keeps its snapshot until its full-site build succeeds, and that can
    # happen long after it first expired.
    # Admin-deleted projects have no files left (project_deletion_service).
    project_ids = [
        pid
        for (pid,) in db.query(Project.id)
        .filter(Project.created_at < cutoff, Project.deleted_at.is_(None))
        .all()
    ]
    db.rollback()

    for project_id in project_ids:
        report.projects_checked += 1
        try:
            freed = _cleanup_one(db, project_id, storage_root, now, cutoff, dry_run)
        except Exception as exc:  # one bad project must not stop the rest
            db.rollback()
            logger.exception("storage cleanup failed for project %s", project_id)
            report.errors.append(f"{project_id}: {exc}")
            continue
        if freed is not None:
            report.projects_cleaned += 1
            report.bytes_freed += freed
    return report
