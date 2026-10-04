import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ModelPricing, TokenUsageLog

logger = logging.getLogger(__name__)

# USD per 1M tokens -- seed/fallback only. The `model_pricing` table (admin-
# editable, see get_model_pricing()) is the actual source of truth; this
# dict is what it was backfilled from and what's used if the DB lookup can't
# run. Unknown models fall back to 0.0 rather than guessing, but that's now
# logged instead of silent (a real prior bug: anthropic/claude-opus-5, the
# live config.generation_model, was missing here and every real generation
# call was pricing at $0.00 until Milestone 11's model_pricing table).
MODEL_PRICING_PER_1M: dict[str, dict[str, float]] = {
    "openai/gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "anthropic/claude-sonnet-4.5": {"prompt": 3.00, "completion": 15.00},
    "anthropic/claude-opus-5": {"prompt": 5.00, "completion": 25.00},
}

_warned_unpriced_models: set[str] = set()


def get_model_pricing(db: Session) -> dict[str, dict[str, float]]:
    """Merges admin-configured `model_pricing` rows over the hardcoded seed
    dict (DB wins on conflict)."""
    merged = dict(MODEL_PRICING_PER_1M)
    rows = db.scalars(select(ModelPricing)).all()
    for row in rows:
        merged[row.model_name] = {
            "prompt": float(row.prompt_price_per_1m),
            "completion": float(row.completion_price_per_1m),
        }
    return merged


def estimate_cost_usd(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing: dict[str, dict[str, float]] | None = None,
) -> float:
    pricing = pricing if pricing is not None else MODEL_PRICING_PER_1M
    model_pricing = pricing.get(model_name)
    if model_pricing is None:
        if model_name not in _warned_unpriced_models:
            logger.warning("no pricing configured for model %s -- costing at $0.00", model_name)
            _warned_unpriced_models.add(model_name)
        model_pricing = {"prompt": 0.0, "completion": 0.0}
    return (
        prompt_tokens * model_pricing["prompt"] + completion_tokens * model_pricing["completion"]
    ) / 1_000_000


def record_usage(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    job_id: uuid.UUID | None,
    model_name: str,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> TokenUsageLog:
    """Adds a TokenUsageLog row to the session (does not commit -- the caller
    persists it as part of its own existing transaction). Internal-only
    bookkeeping, never exposed via an API."""
    pricing = get_model_pricing(db)
    log = TokenUsageLog(
        project_id=project_id,
        user_id=user_id,
        job_id=job_id,
        model_name=model_name,
        purpose=purpose,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate_usd=estimate_cost_usd(model_name, prompt_tokens, completion_tokens, pricing),
    )
    db.add(log)
    return log
