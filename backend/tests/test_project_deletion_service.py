"""Admin soft delete: the pure "is something still writing?" guard. The
DB/disk path (soft_delete_project) needs a real Postgres -- Project has
Postgres-only column types the SQLite test DB can't compile."""

from datetime import datetime, timedelta, timezone

from app.services.project_deletion_service import is_project_busy

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


def test_settled_project_is_not_busy():
    for status in ("ready", "failed", "rejected", "awaiting_cost_approval"):
        assert not is_project_busy(status, NOW - timedelta(minutes=1), has_recent_running_job=False, now=NOW)


def test_running_job_makes_project_busy():
    assert is_project_busy("ready", NOW - timedelta(days=3), has_recent_running_job=True, now=NOW)


def test_active_pipeline_is_busy():
    assert is_project_busy("crawling", NOW - timedelta(minutes=5), has_recent_running_job=False, now=NOW)


def test_pipeline_stuck_for_a_day_can_be_deleted():
    assert not is_project_busy("generating", NOW - timedelta(days=2), has_recent_running_job=False, now=NOW)
