"""DB-backed overrides for which OpenRouter model each AI call uses, so a
model can be swapped without a rebuild/redeploy. Only called from the
queue-worker task layer (tasks_generate.py / tasks_blueprint.py), which
already holds a live `db` session -- the resolved model id is then threaded
down as a plain argument into the DB-free ai/ layer (site_generator.py,
blueprint_pipeline.py, blueprint_review.py, openrouter_client.py), so those
stay unit-testable without a DB.

Two independent knobs, mirroring how the calls themselves are split:
- get_generation_model(tier_key): per-tier override, since each tier
  already runs its own prompt strategy (site_generator.py) -- backed by
  tiers.generation_model (NULL falls back to config.py's default).
- get_vision_model(): one shared override for every blueprint_review.py
  call (meta/content/gap-check), since none of those are tier-specific --
  backed by the ai_model_settings row keyed "vision_model" (a missing row
  falls back to config.py's default).

Follows the same DB-wins-over-hardcoded-default shape as
token_usage_service.get_model_pricing / ModelPricing.
"""

import uuid

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.session import SessionLocal
from ..models import AIModelSetting
from . import tier_service

VISION_MODEL_KEY = "vision_model"


def _with_session(db: Session | None, fn):
    if db is not None:
        return fn(db)
    session = SessionLocal()
    try:
        return fn(session)
    finally:
        session.close()


def get_generation_model(tier_key: str, db: Session | None = None) -> str:
    tier = tier_service.get_tier(tier_key, db)
    if tier is not None and tier.generation_model:
        return tier.generation_model
    return get_settings().generation_model


def get_vision_model(db: Session | None = None) -> str:
    def _query(session: Session) -> str | None:
        row = session.get(AIModelSetting, VISION_MODEL_KEY)
        return row.model_name if row is not None else None

    override = _with_session(db, _query)
    return override or get_settings().vision_model


def set_vision_model(model_name: str, admin_id: uuid.UUID, db: Session | None = None) -> AIModelSetting:
    """Admin write path -- upserts the ai_model_settings row keyed
    VISION_MODEL_KEY. Unlike the read helpers above, a self-opened session
    (db=None) commits before closing, since a write must not be silently
    lost just because the caller didn't pass an existing session."""
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        row = session.get(AIModelSetting, VISION_MODEL_KEY)
        if row is None:
            row = AIModelSetting(key=VISION_MODEL_KEY, model_name=model_name, updated_by_admin_id=admin_id)
            session.add(row)
        else:
            row.model_name = model_name
            row.updated_by_admin_id = admin_id
        session.flush()
        if owns_session:
            session.commit()
        return row
    finally:
        if owns_session:
            session.close()
