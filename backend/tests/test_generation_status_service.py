import types
import uuid

from app.services import generation_status_service as gss
from app.services.generation_status_service import TierOutcome


def _outcomes(**by_tier: str) -> dict[str, TierOutcome]:
    return {
        tier: TierOutcome(tier=tier, status=status, failure_reason="boom" if status == "failed" else None)
        for tier, status in by_tier.items()
    }


def test_all_tiers_succeeded_is_ready():
    status = gss.resolve_project_status({"basic", "premium"}, _outcomes(basic="succeeded", premium="succeeded"))

    assert status == "ready"


def test_one_failed_tier_still_resolves_ready_when_another_succeeded():
    # The whole point: a single tier failing must not sink a project whose
    # other tiers produced real, previewable output.
    status = gss.resolve_project_status(
        {"basic", "premium", "pro"}, _outcomes(basic="succeeded", premium="succeeded", pro="failed")
    )

    assert status == "ready"


def test_every_tier_failed_is_a_project_failure():
    status = gss.resolve_project_status({"basic", "pro"}, _outcomes(basic="failed", pro="failed"))

    assert status == "failed"


def test_still_generating_while_a_tier_is_running():
    status = gss.resolve_project_status(
        {"basic", "pro"}, _outcomes(basic="succeeded", pro="running")
    )

    assert status == "generating"


def test_still_generating_when_a_tier_has_no_job_yet():
    status = gss.resolve_project_status({"basic", "pro"}, _outcomes(basic="succeeded"))

    assert status == "generating"


def test_a_disabled_tiers_failure_does_not_affect_the_project():
    # "pro" failed but is no longer enabled -- the enabled set is what counts.
    status = gss.resolve_project_status({"basic"}, _outcomes(basic="succeeded", pro="failed"))

    assert status == "ready"


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _model):
        return _FakeQuery(self._rows)


def _job(tier: str, status: str, failure_reason: str | None = None):
    return types.SimpleNamespace(tier=tier, overall_status=status, failure_reason=failure_reason)


def test_latest_job_per_tier_wins_so_a_retry_supersedes_its_failed_attempt():
    # Rows arrive newest-first (the query orders by created_at desc), so the
    # running retry is what counts, not the failed attempt it replaced.
    db = _FakeSession([_job("pro", "running"), _job("pro", "failed", "boom")])

    outcomes = gss.get_preview_tier_outcomes(db, uuid.uuid4())

    assert outcomes["pro"].status == "running"


def test_failure_reason_is_carried_through_for_the_latest_attempt():
    db = _FakeSession([_job("pro", "failed", "OpenRouter stalled"), _job("basic", "succeeded")])

    outcomes = gss.get_preview_tier_outcomes(db, uuid.uuid4())

    assert outcomes["pro"].failure_reason == "OpenRouter stalled"
    assert outcomes["basic"].failure_reason is None
