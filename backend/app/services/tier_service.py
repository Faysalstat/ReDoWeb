"""Tier registry -- DB-backed via the `tiers` table (Milestone 11).

Every function keeps its original zero-argument call shape (an optional
trailing `db` opens a short-lived session when the caller doesn't already
have one open), so the existing call sites in routers/projects.py and
routers/downloads.py needed no changes when this moved off the hardcoded
list that used to live here. The public return shape is still the frozen
`Tier` dataclass -- callers do `tier.key`/`tier.is_active`/etc regardless of
where the data actually comes from.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.session import SessionLocal
from ..models import Tier as TierORM


@dataclass(frozen=True)
class Tier:
    key: str
    label: str
    is_active: bool
    sort_order: int
    download_credit_cost: int
    generation_model: str | None


def _to_dataclass(row: TierORM) -> Tier:
    return Tier(
        key=row.key,
        label=row.label,
        is_active=row.is_active,
        sort_order=row.sort_order,
        download_credit_cost=row.download_credit_cost,
        generation_model=row.generation_model,
    )


def _with_session(db: Session | None, fn):
    if db is not None:
        return fn(db)
    session = SessionLocal()
    try:
        return fn(session)
    finally:
        session.close()


def get_all_tiers(db: Session | None = None) -> list[Tier]:
    """All known tiers regardless of enabled state, ordered for display."""

    def _query(session: Session) -> list[Tier]:
        rows = session.scalars(select(TierORM).order_by(TierORM.sort_order)).all()
        return [_to_dataclass(row) for row in rows]

    return _with_session(db, _query)


def get_enabled_tiers(db: Session | None = None) -> list[Tier]:
    """Tiers that should actually be generated/previewed right now."""
    return [tier for tier in get_all_tiers(db) if tier.is_active]


def get_tier(key: str, db: Session | None = None) -> Tier | None:
    def _query(session: Session) -> Tier | None:
        row = session.scalar(select(TierORM).where(TierORM.key == key))
        return _to_dataclass(row) if row is not None else None

    return _with_session(db, _query)


def is_tier_enabled(key: str, db: Session | None = None) -> bool:
    tier = get_tier(key, db)
    return tier is not None and tier.is_active
