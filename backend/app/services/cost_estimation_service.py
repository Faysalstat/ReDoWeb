"""Pre-generation USD cost estimation for the tiered home-page generation
step (see docs/generation-cost-gate-plan.md). Estimates total OpenRouter
spend across all enabled tiers from the deterministic, already-known
design.md text -- before any tier's agent loop (site_generator.py's
_run_agent_loop) actually runs -- so tasks_blueprint.py can gate an
unusually expensive generation behind an admin-configurable USD threshold
(cost_settings_service) and a wallet-balance check.

No tokenizer dependency: the real generation models are OpenRouter-routed
(config.generation_model, per-tier overrides), not a fixed tokenizer
family, so a library like tiktoken would give false precision. Instead this
uses a chars-per-token ratio (plus iteration count and completion-token
size) self-calibrated from this project's own historical TokenUsageLog /
GenerationOutput rows per (model, tier), falling back to conservative
constants when there isn't enough history yet (cold start).

Deliberately conservative: prompt tokens are estimated as
design_md_chars/chars_per_token *per iteration*, summed linearly across the
calibrated iteration count. Real runs benefit from
settings.generation_prompt_caching_enabled cutting repeated-prefix cost
across iterations, which this ignores -- so the estimate errs toward
OVER-estimating, the safer direction for a spend gate, not toward
precision.
"""

import math
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import GenerationJob, GenerationOutput, TokenUsageLog
from . import model_config_service, token_usage_service

DEFAULT_CHARS_PER_TOKEN = 4.0
DEFAULT_ESTIMATED_ITERATIONS = 3
DEFAULT_COMPLETION_TOKENS = 6000
MIN_CALIBRATION_SAMPLES = 3
CALIBRATION_SAMPLE_SIZE = 20


@dataclass(frozen=True)
class TierCostEstimate:
    tier_key: str
    model_name: str
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_cost_usd: float
    calibrated: bool


@dataclass(frozen=True)
class GenerationCostEstimate:
    total_estimated_cost_usd: float
    per_tier: list[TierCostEstimate]


@dataclass(frozen=True)
class CostGateInfo:
    estimated_cost_usd: float
    required_credits: int
    current_balance: int
    shortfall_credits: int


@dataclass(frozen=True)
class _CalibrationSample:
    design_md_chars: int
    prompt_tokens: int
    completion_tokens: int
    iterations: int


def _calibration_samples(db: Session, model_name: str, tier_key: str) -> list[_CalibrationSample]:
    """Recent real generation jobs for this exact (model, tier), each
    contributing one (design.md size, actual tokens used, iteration count)
    data point. Skips rows whose design.md is no longer on disk -- storage
    isn't guaranteed to retain every past project forever."""
    rows = (
        db.query(TokenUsageLog, GenerationJob, GenerationOutput)
        .join(GenerationJob, TokenUsageLog.job_id == GenerationJob.id)
        .join(GenerationOutput, GenerationOutput.job_id == GenerationJob.id)
        .filter(
            TokenUsageLog.purpose == "generation",
            TokenUsageLog.model_name == model_name,
            GenerationJob.tier == tier_key,
        )
        .order_by(TokenUsageLog.created_at.desc())
        .limit(CALIBRATION_SAMPLE_SIZE)
        .all()
    )
    samples = []
    for usage_log, job, output in rows:
        if usage_log.prompt_tokens <= 0:
            continue
        blueprint = job.blueprint
        if blueprint is None or not blueprint.design_md_storage_path:
            continue
        path = Path(blueprint.design_md_storage_path)
        if not path.exists():
            continue
        char_count = len(path.read_text(encoding="utf-8"))
        if char_count <= 0:
            continue
        samples.append(
            _CalibrationSample(
                design_md_chars=char_count,
                prompt_tokens=usage_log.prompt_tokens,
                completion_tokens=usage_log.completion_tokens,
                iterations=output.iterations,
            )
        )
    return samples


def _estimate_tier_inputs(db: Session, model_name: str, tier_key: str) -> tuple[float, int, int, bool]:
    """Returns (chars_per_token, iterations, completion_tokens, calibrated).
    Falls back to the module's DEFAULT_* constants when fewer than
    MIN_CALIBRATION_SAMPLES usable historical samples exist."""
    samples = _calibration_samples(db, model_name, tier_key)
    if len(samples) < MIN_CALIBRATION_SAMPLES:
        return DEFAULT_CHARS_PER_TOKEN, DEFAULT_ESTIMATED_ITERATIONS, DEFAULT_COMPLETION_TOKENS, False

    chars_per_token = sum(s.design_md_chars / s.prompt_tokens for s in samples) / len(samples)
    avg_iterations = round(sum(s.iterations for s in samples) / len(samples))
    avg_completion_tokens = round(sum(s.completion_tokens for s in samples) / len(samples))
    return chars_per_token, max(avg_iterations, 1), max(avg_completion_tokens, 1), True


def _estimate_tier_cost(
    *,
    tier_key: str,
    model_name: str,
    design_md_char_count: int,
    chars_per_token: float,
    iterations: int,
    completion_tokens: int,
    max_iterations: int,
    pricing: dict[str, dict[str, float]],
    calibrated: bool,
) -> TierCostEstimate:
    """Pure math given already-resolved inputs -- unit-testable without a
    DB. `iterations` is always capped at `max_iterations`
    (settings.generation_max_iterations) regardless of calibration, since
    the real agent loop can never exceed it either."""
    capped_iterations = min(iterations, max_iterations)
    estimated_prompt_tokens = round(design_md_char_count / chars_per_token) * capped_iterations
    cost = token_usage_service.estimate_cost_usd(model_name, estimated_prompt_tokens, completion_tokens, pricing)
    return TierCostEstimate(
        tier_key=tier_key,
        model_name=model_name,
        estimated_prompt_tokens=estimated_prompt_tokens,
        estimated_completion_tokens=completion_tokens,
        estimated_cost_usd=cost,
        calibrated=calibrated,
    )


def estimate_generation_cost(db: Session, tier_keys: list[str], design_md: str) -> GenerationCostEstimate:
    """Total estimated USD cost of generating every tier in `tier_keys`
    from `design_md` -- the same text site_generator.py's agent loop is fed
    (see project_root/blueprint/design.md), read by the caller before any
    tier's generate_tier job runs."""
    settings = get_settings()
    pricing = token_usage_service.get_model_pricing(db)
    design_md_char_count = len(design_md)

    per_tier = []
    for tier_key in tier_keys:
        model_name = model_config_service.get_generation_model(tier_key, db)
        chars_per_token, iterations, completion_tokens, calibrated = _estimate_tier_inputs(
            db, model_name, tier_key
        )
        per_tier.append(
            _estimate_tier_cost(
                tier_key=tier_key,
                model_name=model_name,
                design_md_char_count=design_md_char_count,
                chars_per_token=chars_per_token,
                iterations=iterations,
                completion_tokens=completion_tokens,
                max_iterations=settings.generation_max_iterations,
                pricing=pricing,
                calibrated=calibrated,
            )
        )

    return GenerationCostEstimate(
        total_estimated_cost_usd=sum(t.estimated_cost_usd for t in per_tier),
        per_tier=per_tier,
    )


def compute_cost_gate_info(estimated_cost_usd: float, wallet_balance: int, usd_per_credit: float) -> CostGateInfo:
    """Pure conversion from an already-persisted estimate into a required
    credit balance -- shared by the approval endpoint and the status-poll
    endpoint (routers/projects.py) so this math lives in exactly one
    place. `usd_per_credit` is read live at call time (cost_settings_service),
    never snapshotted, so an admin rate change applies immediately to any
    pending project."""
    rate = usd_per_credit if usd_per_credit > 0 else 1.0
    required_credits = math.ceil(estimated_cost_usd / rate)
    shortfall_credits = max(0, required_credits - wallet_balance)
    return CostGateInfo(
        estimated_cost_usd=estimated_cost_usd,
        required_credits=required_credits,
        current_balance=wallet_balance,
        shortfall_credits=shortfall_credits,
    )
