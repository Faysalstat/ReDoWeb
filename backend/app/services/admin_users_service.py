"""Admin user-browsing queries -- a distinct query surface from
admin_analytics_service (dashboard aggregates), but follows the same
"routers stay thin, service holds SQL" convention."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CreditTransaction, CreditWallet, Project, User
from . import admin_analytics_service, wallet_service


@dataclass
class UserListItem:
    user_id: uuid.UUID
    email: str
    is_admin: bool
    is_active: bool
    wallet_balance: int
    projects_count: int
    created_at: datetime


@dataclass
class UserListPage:
    items: list[UserListItem]
    total: int


def list_users(db: Session, *, search: str | None = None, page: int = 1, page_size: int = 25) -> UserListPage:
    query = select(User)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = list(
        db.scalars(query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    )
    user_ids = [u.id for u in users]

    balances: dict[uuid.UUID, int] = {}
    if user_ids:
        for user_id, balance in db.execute(
            select(CreditWallet.user_id, CreditWallet.balance).where(CreditWallet.user_id.in_(user_ids))
        ).all():
            balances[user_id] = balance

    project_counts: dict[uuid.UUID, int] = {}
    if user_ids:
        for user_id, count in db.execute(
            select(Project.user_id, func.count(Project.id))
            .where(Project.user_id.in_(user_ids))
            .group_by(Project.user_id)
        ).all():
            project_counts[user_id] = count

    items = [
        UserListItem(
            user_id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            is_active=user.is_active,
            wallet_balance=balances.get(user.id, 0),
            projects_count=project_counts.get(user.id, 0),
            created_at=user.created_at,
        )
        for user in users
    ]
    return UserListPage(items=items, total=total)


@dataclass
class UserDetail:
    user: User
    wallet_balance: int
    ledger: list[CreditTransaction]
    projects: admin_analytics_service.ProjectListPage


def get_user_detail(db: Session, user_id: uuid.UUID) -> UserDetail | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    wallet = wallet_service.get_or_create_wallet(db, user_id)
    ledger = list(
        db.scalars(
            select(CreditTransaction)
            .where(CreditTransaction.wallet_id == wallet.id)
            .order_by(CreditTransaction.created_at.desc())
        ).all()
    )
    projects = admin_analytics_service.list_projects(db, user_id=user_id, page=1, page_size=100)

    return UserDetail(user=user, wallet_balance=wallet.balance, ledger=ledger, projects=projects)
