"""Aggregation queries backing the admin dashboard. Routers stay thin (parse
-> call service -> return schema) per this repo's existing convention --
this module is where the actual SQL lives."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Blueprint, CreditWallet, GenerationJob, Project, Purchase, TokenUsageLog, User


@dataclass
class OverviewStats:
    users_total: int
    users_new_in_range: int
    projects_total: int
    projects_in_range: int
    generation_success_rate_pct: float | None
    ai_cost_usd_in_range: float
    ai_cost_usd_all_time: float
    revenue_usd_in_range: float
    revenue_usd_all_time: float
    net_margin_usd_in_range: float
    credits_outstanding: int
    active_jobs_running: int


def get_overview(db: Session, days: int) -> OverviewStats:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    users_total = db.scalar(select(func.count(User.id))) or 0
    users_new_in_range = db.scalar(select(func.count(User.id)).where(User.created_at >= since)) or 0

    projects_total = db.scalar(select(func.count(Project.id))) or 0
    projects_in_range = (
        db.scalar(select(func.count(Project.id)).where(Project.created_at >= since)) or 0
    )

    success_rate = _generation_success_rate_pct(db, since)

    ai_cost_in_range = (
        db.scalar(
            select(func.coalesce(func.sum(TokenUsageLog.cost_estimate_usd), 0)).where(
                TokenUsageLog.created_at >= since
            )
        )
        or 0.0
    )
    ai_cost_all_time = (
        db.scalar(select(func.coalesce(func.sum(TokenUsageLog.cost_estimate_usd), 0))) or 0.0
    )

    revenue_in_range_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Purchase.amount_usd_cents), 0)).where(
                Purchase.status == "completed", Purchase.created_at >= since
            )
        )
        or 0
    )
    revenue_all_time_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Purchase.amount_usd_cents), 0)).where(
                Purchase.status == "completed"
            )
        )
        or 0
    )
    revenue_in_range = revenue_in_range_cents / 100
    revenue_all_time = revenue_all_time_cents / 100

    credits_outstanding = db.scalar(select(func.coalesce(func.sum(CreditWallet.balance), 0))) or 0

    active_jobs_running = (
        db.scalar(select(func.count(GenerationJob.id)).where(GenerationJob.overall_status == "running"))
        or 0
    )

    return OverviewStats(
        users_total=users_total,
        users_new_in_range=users_new_in_range,
        projects_total=projects_total,
        projects_in_range=projects_in_range,
        generation_success_rate_pct=success_rate,
        ai_cost_usd_in_range=float(ai_cost_in_range),
        ai_cost_usd_all_time=float(ai_cost_all_time),
        revenue_usd_in_range=float(revenue_in_range),
        revenue_usd_all_time=float(revenue_all_time),
        net_margin_usd_in_range=float(revenue_in_range) - float(ai_cost_in_range),
        credits_outstanding=credits_outstanding,
        active_jobs_running=active_jobs_running,
    )


@dataclass
class ProjectListItem:
    project_id: uuid.UUID
    source_url: str
    status: str
    owner_email: str
    tier: str | None
    created_at: datetime


@dataclass
class ProjectListPage:
    items: list[ProjectListItem]
    total: int


def list_projects(
    db: Session,
    *,
    status: str | None = None,
    tier: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> ProjectListPage:
    """Cross-user project browse for the admin dashboard -- unlike
    GET /api/v1/projects (current user's own list only), this has no
    ownership filter. `tier` filters on the most recent GenerationJob.tier
    per project, same "latest tier" idea routers/projects.py::list_projects
    already uses for the regular per-user list."""
    query = select(Project, User.email).join(User, Project.user_id == User.id)
    if status:
        query = query.where(Project.status == status)
    if search:
        query = query.where(Project.source_url.ilike(f"%{search}%"))

    if tier:
        # Only projects whose most recent generation job used this tier.
        latest_job_ids = (
            select(func.max(GenerationJob.id))
            .group_by(GenerationJob.project_id)
            .where(GenerationJob.tier == tier)
        )
        query = query.where(
            Project.id.in_(select(GenerationJob.project_id).where(GenerationJob.id.in_(latest_job_ids)))
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    rows = db.execute(
        query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    project_ids = [p.id for p, _ in rows]

    jobs = (
        db.execute(
            select(GenerationJob.project_id, GenerationJob.tier)
            .where(GenerationJob.project_id.in_(project_ids))
            .order_by(GenerationJob.created_at.desc())
        ).all()
        if project_ids
        else []
    )
    latest_tier_by_project: dict[uuid.UUID, str] = {}
    for project_id, job_tier in jobs:
        latest_tier_by_project.setdefault(project_id, job_tier)

    items = [
        ProjectListItem(
            project_id=project.id,
            source_url=project.source_url,
            status=project.status,
            owner_email=email,
            tier=latest_tier_by_project.get(project.id),
            created_at=project.created_at,
        )
        for project, email in rows
    ]
    return ProjectListPage(items=items, total=total)


def get_project_detail(db: Session, project_id: uuid.UUID) -> tuple[Project, User, Blueprint | None, list[GenerationJob]] | None:
    """No ownership check here -- callers (the admin router) are already
    gated by require_admin, unlike GET /api/v1/projects/{id}, which enforces
    per-user ownership."""
    row = db.execute(select(Project, User).join(User, Project.user_id == User.id).where(Project.id == project_id)).one_or_none()
    if row is None:
        return None
    project, owner = row

    blueprint = db.scalar(
        select(Blueprint).where(Blueprint.project_id == project.id, Blueprint.is_current.is_(True))
    )

    jobs = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.project_id == project.id)
        .order_by(GenerationJob.created_at.desc())
    ).all()

    return project, owner, blueprint, list(jobs)


def _generation_success_rate_pct(db: Session, since: datetime) -> float | None:
    rows = db.execute(
        select(GenerationJob.overall_status, func.count())
        .where(GenerationJob.created_at >= since, GenerationJob.overall_status.in_(["succeeded", "failed"]))
        .group_by(GenerationJob.overall_status)
    ).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values())
    if total == 0:
        return None
    return round(counts.get("succeeded", 0) / total * 100, 1)
