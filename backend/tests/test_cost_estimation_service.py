from app.services import cost_estimation_service as ces

PRICING = {"test/model": {"prompt": 3.0, "completion": 15.0}}  # $ per 1M tokens


def test_estimate_tier_cost_computes_prompt_tokens_from_chars_and_iterations():
    estimate = ces._estimate_tier_cost(
        tier_key="pro",
        model_name="test/model",
        design_md_char_count=4000,
        chars_per_token=4.0,
        iterations=3,
        completion_tokens=1000,
        max_iterations=24,
        pricing=PRICING,
        calibrated=True,
    )

    # 4000 chars / 4 chars-per-token = 1000 tokens/iteration * 3 iterations
    assert estimate.estimated_prompt_tokens == 3000
    assert estimate.estimated_completion_tokens == 1000
    assert estimate.estimated_cost_usd == (3000 * 3.0 + 1000 * 15.0) / 1_000_000
    assert estimate.calibrated is True


def test_estimate_tier_cost_caps_iterations_at_max_iterations():
    estimate = ces._estimate_tier_cost(
        tier_key="pro",
        model_name="test/model",
        design_md_char_count=4000,
        chars_per_token=4.0,
        iterations=50,
        completion_tokens=1000,
        max_iterations=5,
        pricing=PRICING,
        calibrated=False,
    )

    assert estimate.estimated_prompt_tokens == 1000 * 5


def test_compute_cost_gate_info_sufficient_balance_has_no_shortfall():
    info = ces.compute_cost_gate_info(estimated_cost_usd=2.0, wallet_balance=5, usd_per_credit=1.0)

    assert info.required_credits == 2
    assert info.shortfall_credits == 0


def test_compute_cost_gate_info_insufficient_balance_reports_shortfall():
    info = ces.compute_cost_gate_info(estimated_cost_usd=5.0, wallet_balance=1, usd_per_credit=1.0)

    assert info.required_credits == 5
    assert info.shortfall_credits == 4


def test_compute_cost_gate_info_rounds_required_credits_up():
    # $2.50 at $1/credit -> 3 credits required (never round down a spend gate)
    info = ces.compute_cost_gate_info(estimated_cost_usd=2.5, wallet_balance=3, usd_per_credit=1.0)

    assert info.required_credits == 3
    assert info.shortfall_credits == 0


def test_compute_cost_gate_info_treats_non_positive_rate_as_one_dollar_per_credit():
    info = ces.compute_cost_gate_info(estimated_cost_usd=2.0, wallet_balance=0, usd_per_credit=0.0)

    assert info.required_credits == 2


def test_estimate_tier_inputs_falls_back_to_defaults_when_no_calibration_history(monkeypatch):
    monkeypatch.setattr(ces, "_calibration_samples", lambda db, model_name, tier_key: [])

    chars_per_token, iterations, completion_tokens, calibrated = ces._estimate_tier_inputs(
        db=None, model_name="test/model", tier_key="pro"
    )

    assert chars_per_token == ces.DEFAULT_CHARS_PER_TOKEN
    assert iterations == ces.DEFAULT_ESTIMATED_ITERATIONS
    assert completion_tokens == ces.DEFAULT_COMPLETION_TOKENS
    assert calibrated is False


def test_estimate_tier_inputs_calibrates_from_history_when_enough_samples(monkeypatch):
    samples = [
        ces._CalibrationSample(design_md_chars=4000, prompt_tokens=1000, completion_tokens=2000, iterations=4),
        ces._CalibrationSample(design_md_chars=8000, prompt_tokens=2000, completion_tokens=3000, iterations=6),
        ces._CalibrationSample(design_md_chars=2000, prompt_tokens=500, completion_tokens=1000, iterations=2),
    ]
    monkeypatch.setattr(ces, "_calibration_samples", lambda db, model_name, tier_key: samples)

    chars_per_token, iterations, completion_tokens, calibrated = ces._estimate_tier_inputs(
        db=None, model_name="test/model", tier_key="pro"
    )

    assert calibrated is True
    # each sample's chars/prompt_tokens ratio is exactly 4.0
    assert chars_per_token == 4.0
    assert iterations == round((4 + 6 + 2) / 3)
    assert completion_tokens == round((2000 + 3000 + 1000) / 3)


def test_estimate_generation_cost_sums_across_tiers_using_cold_start_defaults(monkeypatch):
    monkeypatch.setattr(ces, "_calibration_samples", lambda db, model_name, tier_key: [])

    class FakeSettings:
        generation_max_iterations = 24

    monkeypatch.setattr(ces, "get_settings", lambda: FakeSettings())

    from app.services import model_config_service, token_usage_service

    monkeypatch.setattr(model_config_service, "get_generation_model", lambda tier_key, db: "test/model")
    monkeypatch.setattr(token_usage_service, "get_model_pricing", lambda db: PRICING)

    result = ces.estimate_generation_cost(db=None, tier_keys=["premium", "pro"], design_md="x" * 4000)

    assert [t.tier_key for t in result.per_tier] == ["premium", "pro"]
    assert result.total_estimated_cost_usd == sum(t.estimated_cost_usd for t in result.per_tier)
    assert all(t.calibrated is False for t in result.per_tier)
