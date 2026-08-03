import uuid

from sqlalchemy.orm import Session

from ..models import TokenUsageLog

# USD per 1M tokens. Covers the two models currently configured
# (config.vision_model / config.generation_model); unknown models fall back
# to 0.0 rather than guessing -- this is a rough internal cost estimate, not
# billing-grade accounting.
MODEL_PRICING_PER_1M: dict[str, dict[str, float]] = {
    "openai/gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "anthropic/claude-sonnet-4.5": {"prompt": 3.00, "completion": 15.00},
}


def estimate_cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING_PER_1M.get(model_name, {"prompt": 0.0, "completion": 0.0})
    return (prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]) / 1_000_000


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
    log = TokenUsageLog(
        project_id=project_id,
        user_id=user_id,
        job_id=job_id,
        model_name=model_name,
        purpose=purpose,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate_usd=estimate_cost_usd(model_name, prompt_tokens, completion_tokens),
    )
    db.add(log)
    return log
