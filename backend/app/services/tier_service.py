"""Tier registry -- DB-backed via the `tiers` table (Milestone 11).

Every function keeps its original zero-argument call shape (an optional
trailing `db` opens a short-lived session when the caller doesn't already
have one open), so the existing call sites in routers/projects.py and
routers/downloads.py needed no changes when this moved off the hardcoded
list that used to live here. The public return shape is still the frozen
`Tier` dataclass -- callers do `tier.key`/`tier.is_active`/etc regardless of
where the data actually comes from.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

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
    updated_at: datetime
    updated_by_admin_id: uuid.UUID | None


def _to_dataclass(row: TierORM) -> Tier:
    return Tier(
        key=row.key,
        label=row.label,
        is_active=row.is_active,
        sort_order=row.sort_order,
        download_credit_cost=row.download_credit_cost,
        generation_model=row.generation_model,
        updated_at=row.updated_at,
        updated_by_admin_id=row.updated_by_admin_id,
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


def set_generation_model(
    key: str, model_name: str | None, admin_id: uuid.UUID, db: Session | None = None
) -> Tier:
    """Admin write path -- model_name=None clears the override back to
    config.py's default (model_config_service.get_generation_model already
    handles a NULL column that way). Raises ValueError if the tier key
    doesn't exist (the router maps this to a 404). Unlike the read helpers
    above, a self-opened session (db=None) commits before closing -- a
    write must not be silently lost just because the caller didn't pass an
    existing session."""
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        row = session.scalar(select(TierORM).where(TierORM.key == key))
        if row is None:
            raise ValueError(f"no tier with key {key!r}")
        row.generation_model = model_name
        row.updated_by_admin_id = admin_id
        session.flush()
        result = _to_dataclass(row)
        if owns_session:
            session.commit()
        return result
    finally:
        if owns_session:
            session.close()


MIN_DOWNLOAD_CREDIT_COST = 1
MAX_LABEL_LENGTH = 64


def update_tier(
    key: str,
    *,
    label: str,
    sort_order: int,
    download_credit_cost: int,
    admin_id: uuid.UUID,
    db: Session | None = None,
) -> Tier:
    """Admin write path for the Tiers & pricing page: display label, display
    order and download cost in one save. `key` itself is never editable --
    it's embedded in storage paths and generation_jobs.tier. Raises
    LookupError for an unknown key, ValueError for an invalid value."""
    cleaned = (label or "").strip()
    if not cleaned or len(cleaned) > MAX_LABEL_LENGTH:
        raise ValueError(f"label must be 1-{MAX_LABEL_LENGTH} characters")
    if download_credit_cost < MIN_DOWNLOAD_CREDIT_COST:
        raise ValueError(f"download cost must be at least {MIN_DOWNLOAD_CREDIT_COST}")
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        row = session.scalar(select(TierORM).where(TierORM.key == key))
        if row is None:
            raise LookupError(f"no tier with key {key!r}")
        row.label = cleaned
        row.sort_order = sort_order
        row.download_credit_cost = download_credit_cost
        row.updated_by_admin_id = admin_id
        session.flush()
        result = _to_dataclass(row)
        if owns_session:
            session.commit()
        return result
    finally:
        if owns_session:
            session.close()


def set_active(
    key: str, is_active: bool, admin_id: uuid.UUID, db: Session | None = None
) -> Tier:
    """Admin write path -- enable/disable a tier. A disabled tier is skipped
    entirely by get_enabled_tiers()/is_tier_enabled(), the one place tier-
    enabled logic lives, so this takes effect on the very next submission
    with no other code changes needed. Raises ValueError if the tier key
    doesn't exist (the router maps this to a 404)."""
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        row = session.scalar(select(TierORM).where(TierORM.key == key))
        if row is None:
            raise ValueError(f"no tier with key {key!r}")
        row.is_active = is_active
        row.updated_by_admin_id = admin_id
        session.flush()
        result = _to_dataclass(row)
        if owns_session:
            session.commit()
        return result
    finally:
        if owns_session:
            session.close()
