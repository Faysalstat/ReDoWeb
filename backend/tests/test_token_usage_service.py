import uuid

from app.services.token_usage_service import estimate_cost_usd, record_usage


def test_estimate_cost_known_model():
    # gpt-4o-mini: $0.15/$0.60 per 1M prompt/completion tokens
    cost = estimate_cost_usd("openai/gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == 0.75


def test_estimate_cost_zero_tokens():
    assert estimate_cost_usd("anthropic/claude-sonnet-4.5", prompt_tokens=0, completion_tokens=0) == 0.0


def test_estimate_cost_unknown_model_defaults_to_zero():
    assert estimate_cost_usd("some/unlisted-model", prompt_tokens=5000, completion_tokens=5000) == 0.0


def test_record_usage_adds_row_with_computed_cost():
    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

    db = FakeSession()
    project_id, user_id, job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    log = record_usage(
        db,
        project_id=project_id,
        user_id=user_id,
        job_id=job_id,
        model_name="openai/gpt-4o-mini",
        purpose="blueprint_extraction",
        prompt_tokens=2_000_000,
        completion_tokens=1_000_000,
    )

    assert db.added == [log]
    assert log.project_id == project_id
    assert log.user_id == user_id
    assert log.job_id == job_id
    assert log.purpose == "blueprint_extraction"
    # 2M prompt @ $0.15/1M + 1M completion @ $0.60/1M = 0.30 + 0.60
    assert log.cost_estimate_usd == 0.90
