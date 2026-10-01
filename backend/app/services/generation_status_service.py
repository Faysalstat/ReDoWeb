"""Per-tier generation outcomes, and the one place that decides what a
project's overall `status` should be once its tiers have fanned out and
finished independently.

**One tier failing is not a project-level failure.** Every other tier's
output is still real, on disk, and previewable, so a project only reaches
the terminal "failed" status when *every* enabled tier failed. A partial
failure resolves to "ready", with the failed tiers reported per tier
(`ProjectStatusResponse.tier_failures`) and individually retryable via
`POST /projects/{id}/retry-tier`.

Two filters make this correct:
- Only `scope="preview"` jobs count. A `full_site` job
  (workers/tasks_full_site.py) is a separate post-download build that
  deliberately never touches `project.status`, and its failure must not
  retroactively fail an already-delivered preview.
- Only the *latest* job per tier counts, so a retry cleanly supersedes the
  failed attempt it replaces instead of both being counted forever.
"""

import uuid
from dataclasses import dataclass
from typing import Mapping

from sqlalchemy.orm import Session

from ..models import GenerationJob

SETTLED_STATUSES = ("succeeded", "failed")


@dataclass(frozen=True)
class TierOutcome:
    tier: str
    status: str  # "running" | "succeeded" | "failed"
    failure_reason: str | None


def get_preview_tier_outcomes(db: Session, project_id: uuid.UUID) -> dict[str, TierOutcome]:
    """Latest preview-scope job per tier, keyed by tier."""
    rows = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project_id, GenerationJob.scope == "preview")
        .order_by(GenerationJob.created_at.desc())
        .all()
    )
    outcomes: dict[str, TierOutcome] = {}
    for row in rows:
        if row.tier in outcomes:
            # Rows are newest-first, so the first one seen for a tier is the
            # live attempt -- an earlier failed job it retried is ignored.
            continue
        outcomes[row.tier] = TierOutcome(
            tier=row.tier, status=row.overall_status, failure_reason=row.failure_reason
        )
    return outcomes


def resolve_project_status(enabled_tier_keys: set[str], outcomes: Mapping[str, TierOutcome]) -> str:
    """Pure decision function, kept separate from the DB/task plumbing so
    it's directly unit-testable. Returns "generating" while any enabled
    tier is still unsettled, then "ready" if at least one enabled tier
    succeeded, and only "failed" when every enabled tier failed."""
    settled = {tier for tier, outcome in outcomes.items() if outcome.status in SETTLED_STATUSES}
    if not enabled_tier_keys <= settled:
        return "generating"
    if any(outcomes[tier].status == "succeeded" for tier in enabled_tier_keys):
        return "ready"
    return "failed"
