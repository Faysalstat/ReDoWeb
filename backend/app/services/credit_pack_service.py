"""Admin CRUD for credit packs. Packs are never hard-deleted (a Purchase
references the pack it came from) -- disable instead. Editing a pack never
affects an order already in flight: billing_service.create_order snapshots
credits/price onto the Purchase row at order time."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CreditPack

MAX_NAME_LENGTH = 64


class CreditPackNotFoundError(LookupError):
    pass


def _validate(name: str, credits: int, price_usd_cents: int) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("name is required")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(f"name must be at most {MAX_NAME_LENGTH} characters")
    if credits < 1:
        raise ValueError("credits must be at least 1")
    if price_usd_cents < 1:
        raise ValueError("price must be greater than zero")
    return cleaned


def list_all(db: Session) -> list[CreditPack]:
    return list(db.scalars(select(CreditPack).order_by(CreditPack.sort_order, CreditPack.price_usd_cents)).all())


def create(
    db: Session,
    *,
    name: str,
    credits: int,
    price_usd_cents: int,
    is_active: bool,
    sort_order: int,
    admin_id: uuid.UUID,
) -> CreditPack:
    pack = CreditPack(
        name=_validate(name, credits, price_usd_cents),
        credits=credits,
        price_usd_cents=price_usd_cents,
        is_active=is_active,
        sort_order=sort_order,
        updated_by_admin_id=admin_id,
    )
    db.add(pack)
    db.flush()
    return pack


def update(
    db: Session,
    pack_id: uuid.UUID,
    *,
    name: str,
    credits: int,
    price_usd_cents: int,
    sort_order: int,
    admin_id: uuid.UUID,
) -> CreditPack:
    pack = db.get(CreditPack, pack_id)
    if pack is None:
        raise CreditPackNotFoundError(f"no credit pack {pack_id}")
    pack.name = _validate(name, credits, price_usd_cents)
    pack.credits = credits
    pack.price_usd_cents = price_usd_cents
    pack.sort_order = sort_order
    pack.updated_by_admin_id = admin_id
    db.flush()
    return pack


def set_active(db: Session, pack_id: uuid.UUID, is_active: bool, admin_id: uuid.UUID) -> CreditPack:
    pack = db.get(CreditPack, pack_id)
    if pack is None:
        raise CreditPackNotFoundError(f"no credit pack {pack_id}")
    pack.is_active = is_active
    pack.updated_by_admin_id = admin_id
    db.flush()
    return pack
