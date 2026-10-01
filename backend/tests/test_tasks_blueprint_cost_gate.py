import types

from app.services.cost_estimation_service import GenerationCostEstimate, TierCostEstimate
from app.workers.tasks_blueprint import _apply_cost_gate


def _estimate(total_cost: float) -> GenerationCostEstimate:
    return GenerationCostEstimate(
        total_estimated_cost_usd=total_cost,
        per_tier=[
            TierCostEstimate(
                tier_key="pro",
                model_name="test/model",
                estimated_prompt_tokens=1000,
                estimated_completion_tokens=1000,
                estimated_cost_usd=total_cost,
                calibrated=False,
            )
        ],
    )


def _project():
    return types.SimpleNamespace(
        status="blueprint_ready", estimated_generation_cost_usd=None, pending_tier_keys=None
    )


def test_under_threshold_does_not_gate():
    project = _project()

    gated = _apply_cost_gate(project, ["premium", "pro"], _estimate(0.5), alert_threshold_usd=1.0)

    assert gated is False
    assert project.status == "blueprint_ready"
    assert project.estimated_generation_cost_usd is None
    assert project.pending_tier_keys is None


def test_over_threshold_gates_and_snapshots_tier_keys():
    project = _project()

    gated = _apply_cost_gate(project, ["premium", "pro"], _estimate(5.0), alert_threshold_usd=1.0)

    assert gated is True
    assert project.status == "awaiting_cost_approval"
    assert project.estimated_generation_cost_usd == 5.0
    assert project.pending_tier_keys == ["premium", "pro"]


def test_exactly_at_threshold_does_not_gate():
    # ">" not ">=" in tasks_blueprint.py -- an estimate exactly equal to the
    # threshold is let through rather than blocked.
    project = _project()

    gated = _apply_cost_gate(project, ["pro"], _estimate(1.0), alert_threshold_usd=1.0)

    assert gated is False
    assert project.status == "blueprint_ready"
