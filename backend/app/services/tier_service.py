"""Tier registry.

Tiers are a dynamic, admin-manageable concept, not a fixed Basic/Premium/Pro
enum -- see docs/implementation-plan.md's `tiers` table design. Until the DB
layer is wired up, this module is the *single* place tier data and the
on/off toggle live; every caller (routers, Celery tasks once added) must go
through get_enabled_tiers()/is_tier_enabled() rather than hardcoding a tier
list, so swapping this for a real DB-backed admin-editable table later is a
one-file change.

Current build/test phase: only "pro" is enabled while the generation
mechanism and its prompts are being validated.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    key: str
    label: str
    is_active: bool
    sort_order: int
    download_credit_cost: int


_TIERS: list[Tier] = [
    Tier(key="basic", label="Basic", is_active=False, sort_order=1, download_credit_cost=3),
    Tier(key="premium", label="Premium", is_active=False, sort_order=2, download_credit_cost=5),
    Tier(key="pro", label="Pro", is_active=True, sort_order=3, download_credit_cost=10),
]

_TIERS_BY_KEY = {tier.key: tier for tier in _TIERS}


def get_all_tiers() -> list[Tier]:
    """All known tiers regardless of enabled state, ordered for display."""
    return sorted(_TIERS, key=lambda t: t.sort_order)


def get_enabled_tiers() -> list[Tier]:
    """Tiers that should actually be generated/previewed right now."""
    return [tier for tier in get_all_tiers() if tier.is_active]


def get_tier(key: str) -> Tier | None:
    return _TIERS_BY_KEY.get(key)


def is_tier_enabled(key: str) -> bool:
    tier = get_tier(key)
    return tier is not None and tier.is_active
