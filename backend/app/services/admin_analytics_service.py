"""Aggregation queries backing the admin dashboard. Routers stay thin (parse
-> call service -> return schema) per this repo's existing convention --
this module is where the actual SQL lives."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Blueprint, CreditWallet, GenerationJob, Project, Purchase, TokenUsageLog, User


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


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
    since = _since(days)

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
                Purchase.status == "completed", Purchase.source != "mock", Purchase.created_at >= since
            )
        )
        or 0
    )
    revenue_all_time_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Purchase.amount_usd_cents), 0)).where(
                Purchase.status == "completed", Purchase.source != "mock"
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
    user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> ProjectListPage:
    """Cross-user project browse for the admin dashboard -- unlike
    GET /api/v1/projects (current user's own list only), this has no
    ownership filter. `tier` filters on the most recent GenerationJob.tier
    per project, same "latest tier" idea routers/projects.py::list_projects
    already uses for the regular per-user list. `user_id`, when given,
    scopes to one user's projects -- shared by the Users admin page (a
    user's own history) and a plain cross-user browse (user_id=None)."""
    query = select(Project, User.email).join(User, Project.user_id == User.id)
    if status:
        query = query.where(Project.status == status)
    if search:
        query = query.where(Project.source_url.ilike(f"%{search}%"))
    if user_id:
        query = query.where(Project.user_id == user_id)

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


@dataclass
class JobTokenUsage:
    models_used: list[str] = field(default_factory=list)
    total_cost_usd: float = 0.0


def get_token_usage_by_job(db: Session, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, JobTokenUsage]:
    """Aggregates TokenUsageLog rows per job_id -- a job can span more than
    one AI call/purpose (e.g. blueprint review's vision+content calls plus
    the generation call), so this is the authoritative source for "which
    model(s) this specific job actually used" and its total estimated cost.
    Tier.generation_model/AIModelSetting only reflect the *current* config,
    which can drift after a past job ran, so they're not used here."""
    if not job_ids:
        return {}
    rows = db.execute(
        select(TokenUsageLog.job_id, TokenUsageLog.model_name, TokenUsageLog.cost_estimate_usd).where(
            TokenUsageLog.job_id.in_(job_ids)
        )
    ).all()
    usage: dict[uuid.UUID, JobTokenUsage] = {}
    for job_id, model_name, cost in rows:
        agg = usage.setdefault(job_id, JobTokenUsage())
        if model_name not in agg.models_used:
            agg.models_used.append(model_name)
        agg.total_cost_usd += float(cost)
    return usage


def get_project_detail(
    db: Session, project_id: uuid.UUID
) -> tuple[Project, User, Blueprint | None, list[GenerationJob], dict[uuid.UUID, JobTokenUsage]] | None:
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

    jobs = list(
        db.scalars(
            select(GenerationJob)
            .where(GenerationJob.project_id == project.id)
            .order_by(GenerationJob.created_at.desc())
        ).all()
    )
    token_usage_by_job = get_token_usage_by_job(db, [job.id for job in jobs])

    return project, owner, blueprint, jobs, token_usage_by_job


@dataclass
class ModelCostRow:
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    call_count: int


def cost_by_model(db: Session, days: int) -> list[ModelCostRow]:
    since = _since(days)
    rows = db.execute(
        select(
            TokenUsageLog.model_name,
            func.coalesce(func.sum(TokenUsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(TokenUsageLog.completion_tokens), 0),
            func.coalesce(func.sum(TokenUsageLog.cost_estimate_usd), 0),
            func.count(),
        )
        .where(TokenUsageLog.created_at >= since)
        .group_by(TokenUsageLog.model_name)
        .order_by(func.sum(TokenUsageLog.cost_estimate_usd).desc())
    ).all()
    return [
        ModelCostRow(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=float(cost),
            call_count=call_count,
        )
        for model_name, prompt_tokens, completion_tokens, cost, call_count in rows
    ]


@dataclass
class CostByUserRow:
    user_id: uuid.UUID
    email: str
    cost_usd: float
    call_count: int


@dataclass
class CostByUserPage:
    items: list[CostByUserRow]
    total: int


def cost_by_user(db: Session, days: int, page: int = 1, page_size: int = 25) -> CostByUserPage:
    since = _since(days)
    base = (
        select(
            TokenUsageLog.user_id,
            User.email,
            func.coalesce(func.sum(TokenUsageLog.cost_estimate_usd), 0).label("cost_usd"),
            func.count().label("call_count"),
        )
        .join(User, TokenUsageLog.user_id == User.id)
        .where(TokenUsageLog.created_at >= since)
        .group_by(TokenUsageLog.user_id, User.email)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(func.sum(TokenUsageLog.cost_estimate_usd).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        CostByUserRow(user_id=user_id, email=email, cost_usd=float(cost_usd), call_count=call_count)
        for user_id, email, cost_usd, call_count in rows
    ]
    return CostByUserPage(items=items, total=total)


@dataclass
class CostByProjectRow:
    project_id: uuid.UUID
    source_url: str
    cost_usd: float
    call_count: int


@dataclass
class CostByProjectPage:
    items: list[CostByProjectRow]
    total: int


def cost_by_project(db: Session, days: int, page: int = 1, page_size: int = 25) -> CostByProjectPage:
    since = _since(days)
    base = (
        select(
            TokenUsageLog.project_id,
            Project.source_url,
            func.coalesce(func.sum(TokenUsageLog.cost_estimate_usd), 0).label("cost_usd"),
            func.count().label("call_count"),
        )
        .join(Project, TokenUsageLog.project_id == Project.id)
        .where(TokenUsageLog.created_at >= since)
        .group_by(TokenUsageLog.project_id, Project.source_url)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(func.sum(TokenUsageLog.cost_estimate_usd).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        CostByProjectRow(
            project_id=project_id, source_url=source_url, cost_usd=float(cost_usd), call_count=call_count
        )
        for project_id, source_url, cost_usd, call_count in rows
    ]
    return CostByProjectPage(items=items, total=total)


@dataclass
class RevenueBreakdown:
    revenue_usd_in_range: float
    revenue_usd_all_time: float
    paypal_revenue_usd_in_range: float
    manual_revenue_usd_in_range: float
    purchase_count_in_range: int


def revenue_breakdown(db: Session, days: int) -> RevenueBreakdown:
    since = _since(days)

    def _sum_cents(*, source: str | None = None, since_filter: bool = True) -> int:
        # source="mock" rows are local test payments (payments/mock_gateway.py)
        # -- no money moved, so they never count as revenue.
        query = select(func.coalesce(func.sum(Purchase.amount_usd_cents), 0)).where(
            Purchase.status == "completed", Purchase.source != "mock"
        )
        if since_filter:
            query = query.where(Purchase.created_at >= since)
        if source is not None:
            query = query.where(Purchase.source == source)
        return db.scalar(query) or 0

    purchase_count_in_range = (
        db.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.status == "completed", Purchase.source != "mock", Purchase.created_at >= since
            )
        )
        or 0
    )

    return RevenueBreakdown(
        revenue_usd_in_range=_sum_cents() / 100,
        revenue_usd_all_time=_sum_cents(since_filter=False) / 100,
        paypal_revenue_usd_in_range=_sum_cents(source="paypal") / 100,
        manual_revenue_usd_in_range=_sum_cents(source="manual_admin") / 100,
        purchase_count_in_range=purchase_count_in_range,
    )


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


@dataclass
class PaymentStats:
    purchases_in_range: int
    pending_purchases: int
    refunds_in_range: int
    paying_users: int


def payment_stats(db: Session, days: int) -> PaymentStats:
    """Payment tiles for the admin overview. Gateway purchases only
    (manual_admin adjustments aren't purchases a user made) and never
    source="mock" test payments. Kept separate from get_overview because it
    only touches Purchase rows, so it's unit-testable on SQLite."""
    since = _since(days)
    real = (Purchase.source == "paypal",)

    def _count(*conditions) -> int:
        return db.scalar(select(func.count(Purchase.id)).where(*real, *conditions)) or 0

    return PaymentStats(
        purchases_in_range=_count(Purchase.status == "completed", Purchase.created_at >= since),
        pending_purchases=_count(Purchase.status == "pending"),
        refunds_in_range=_count(Purchase.status == "refunded", Purchase.refunded_at >= since),
        paying_users=db.scalar(
            select(func.count(func.distinct(Purchase.user_id))).where(*real, Purchase.status == "completed")
        )
        or 0,
    )
