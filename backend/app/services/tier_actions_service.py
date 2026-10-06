"""Post-purchase per-tier actions: Download, Generate all pages, Run SEO
(see docs/seo-agent-and-buy-flow-plan.md). The pure decision functions are
kept separate from the DB plumbing so they're directly unit-testable --
Project uses Postgres-only column types, so router-level tests can't run on
the SQLite test DB (same approach as the old _resolve_download_plan)."""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from ..ai.seo_agent import SEO_TIER_KEYS
from ..models import CrawlSnapshot, CreditTransaction, GenerationJob, GenerationOutput, Project
from . import wallet_service
from .job_progress import latest_activity

ActionStatus = Literal["none", "running", "succeeded", "failed"]
FullSiteAction = Literal["not_applicable", "running", "already_done", "start"]
SeoAction = Literal["unavailable", "needs_full_site", "running", "already_done", "start"]


def action_status(job: GenerationJob | None) -> ActionStatus:
    if job is None:
        return "none"
    if job.overall_status in ("running", "succeeded", "failed"):
        return job.overall_status
    return "none"


def resolve_full_site_action(page_count: int, full_site_job: GenerationJob | None) -> FullSiteAction:
    """Generate all pages: only for multi-page sites; runs once per
    purchase -- a retry is allowed only after a failure (user decision
    2026-10-05: no rerun of a succeeded build)."""
    if page_count <= 1:
        return "not_applicable"
    status = action_status(full_site_job)
    if status == "running":
        return "running"
    if status == "succeeded":
        return "already_done"
    return "start"


def resolve_seo_action(
    tier: str, page_count: int, full_site_job: GenerationJob | None, seo_job: GenerationJob | None
) -> SeoAction:
    """Run SEO agent: Pro/Premium only; on a multi-page site only once
    "Generate all pages" has succeeded (so SEO always runs on the final
    site); once per purchase, retry only after a failure."""
    if tier not in SEO_TIER_KEYS:
        return "unavailable"
    if page_count > 1 and action_status(full_site_job) != "succeeded":
        return "needs_full_site"
    status = action_status(seo_job)
    if status == "running":
        return "running"
    if status == "succeeded":
        return "already_done"
    return "start"


def choose_download_scope(
    seo_output: GenerationOutput | None,
    full_site_output: GenerationOutput | None,
    preview_output: GenerationOutput | None,
) -> GenerationOutput | None:
    """The best finished output right now: SEO version, then full site,
    then the home-page preview."""
    return seo_output or full_site_output or preview_output


# --- DB helpers --------------------------------------------------------------


def latest_job(db: Session, project_id: uuid.UUID, tier: str, scope: str) -> GenerationJob | None:
    return (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project_id, GenerationJob.tier == tier, GenerationJob.scope == scope)
        .order_by(GenerationJob.created_at.desc())
        .first()
    )


def latest_succeeded_output(db: Session, project_id: uuid.UUID, tier: str, scope: str) -> GenerationOutput | None:
    job = (
        db.query(GenerationJob)
        .filter(
            GenerationJob.project_id == project_id,
            GenerationJob.tier == tier,
            GenerationJob.scope == scope,
            GenerationJob.overall_status == "succeeded",
        )
        .order_by(GenerationJob.created_at.desc())
        .first()
    )
    return job.output if job is not None else None


def latest_page_count(db: Session, project_id: uuid.UUID) -> int:
    snapshot = (
        db.query(CrawlSnapshot)
        .filter(CrawlSnapshot.project_id == project_id)
        .order_by(CrawlSnapshot.crawl_finished_at.desc())
        .first()
    )
    # Defensive fallback only -- a project that's reached "ready" always has
    # a snapshot; this just avoids a crash if that invariant is ever broken.
    return snapshot.page_count if snapshot is not None else 1


def is_purchased(db: Session, project: Project, tier: str) -> bool:
    """Bought == a download_spend ledger row exists for (project, tier) --
    the same key the purchase writes, so every purchase made before the
    Buy/Download split still counts."""
    key = wallet_service.download_spend_key(project.id, tier)
    return db.query(CreditTransaction.id).filter(CreditTransaction.idempotency_key == key).first() is not None


@dataclass
class TierActions:
    full_site_status: ActionStatus
    full_site_failure_reason: str | None
    seo_available: bool
    seo_status: ActionStatus
    seo_failure_reason: str | None
    seo_progress: dict | None = None


def public_progress(progress: dict | None) -> dict | None:
    """The user-facing slice of a job's progress -- no debug entries (raw
    errors, model names, token counts), and only the last few activity
    lines; admins see the full log on the admin project page."""
    if not progress:
        return None
    return {
        "status": progress.get("status"),
        "step": progress.get("step"),
        "label": progress.get("label"),
        "percent": progress.get("percent", 0),
        "detail": progress.get("detail", ""),
        "steps": [
            {"key": s.get("key"), "label": s.get("label"), "status": s.get("status")}
            for s in progress.get("steps", [])
        ],
        "activity": latest_activity(progress, limit=6),
        "updated_at": progress.get("updated_at"),
    }


def tier_actions(db: Session, project: Project, tier_keys: list[str]) -> dict[str, TierActions]:
    result: dict[str, TierActions] = {}
    for tier in tier_keys:
        full_site_job = latest_job(db, project.id, tier, "full_site")
        seo_job = latest_job(db, project.id, tier, "seo")
        result[tier] = TierActions(
            full_site_status=action_status(full_site_job),
            full_site_failure_reason=full_site_job.failure_reason
            if full_site_job is not None and full_site_job.overall_status == "failed"
            else None,
            seo_available=tier in SEO_TIER_KEYS,
            seo_status=action_status(seo_job),
            seo_failure_reason=seo_job.failure_reason
            if seo_job is not None and seo_job.overall_status == "failed"
            else None,
            seo_progress=public_progress(seo_job.progress) if seo_job is not None else None,
        )
    return result
