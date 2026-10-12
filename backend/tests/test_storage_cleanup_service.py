"""Disk-retention cleanup: the pure decision logic and the filesystem step.
The DB plumbing (_cleanup_one/run_storage_cleanup) isn't covered here --
Project has Postgres-only column types the SQLite test DB can't compile
(same limitation as tier_actions_service's router-level paths)."""

from datetime import datetime, timedelta, timezone

from app.services.storage_cleanup_service import (
    CleanupPlan,
    apply_cleanup_plan,
    is_cleanup_due,
    plan_project_cleanup,
)

NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
CUTOFF = NOW - timedelta(days=45)
OLD = CUTOFF - timedelta(days=1)
RECENT = CUTOFF + timedelta(days=1)


# --- is_cleanup_due ------------------------------------------------------------


def test_recent_project_is_not_due():
    assert not is_cleanup_due("ready", RECENT, RECENT, CUTOFF, has_recent_running_job=False)


def test_old_settled_project_is_due():
    for status in ("ready", "failed", "rejected", "awaiting_cost_approval"):
        assert is_cleanup_due(status, OLD, RECENT, CUTOFF, has_recent_running_job=False)


def test_recent_running_job_blocks_cleanup():
    assert not is_cleanup_due("ready", OLD, OLD, CUTOFF, has_recent_running_job=True)


def test_old_project_mid_pipeline_waits_until_idle_for_whole_window():
    # Still being worked on recently -> leave it alone.
    assert not is_cleanup_due("generating", OLD, RECENT, CUTOFF, has_recent_running_job=False)
    # Stuck mid-pipeline for the whole window -> a dead pipeline, clean it.
    assert is_cleanup_due("generating", OLD, OLD, CUTOFF, has_recent_running_job=False)


# --- plan_project_cleanup ------------------------------------------------------


def test_nothing_bought_deletes_every_preview_and_the_crawl():
    plan = plan_project_cleanup({"pro", "premium"}, set(), page_count=5, full_site_succeeded_tiers=set())
    assert plan.tier_dirs_to_delete == ("premium", "pro")
    assert plan.delete_snapshot
    assert plan.delete_downloads


def test_purchased_tier_is_never_deleted():
    plan = plan_project_cleanup({"pro", "premium"}, {"pro"}, page_count=1, full_site_succeeded_tiers=set())
    assert plan.tier_dirs_to_delete == ("premium",)


def test_single_page_purchase_does_not_need_the_crawl():
    plan = plan_project_cleanup({"pro"}, {"pro"}, page_count=1, full_site_succeeded_tiers=set())
    assert plan.delete_snapshot


def test_multi_page_purchase_keeps_crawl_until_full_site_succeeds():
    # "Generate all pages" copies images from snapshot/ -- still possible.
    pending = plan_project_cleanup({"pro"}, {"pro"}, page_count=4, full_site_succeeded_tiers=set())
    assert not pending.delete_snapshot

    done = plan_project_cleanup({"pro"}, {"pro"}, page_count=4, full_site_succeeded_tiers={"pro"})
    assert done.delete_snapshot


def test_crawl_kept_while_any_purchased_tier_still_needs_it():
    plan = plan_project_cleanup(
        {"pro", "premium"}, {"pro", "premium"}, page_count=4, full_site_succeeded_tiers={"pro"}
    )
    assert plan.tier_dirs_to_delete == ()
    assert not plan.delete_snapshot


# --- apply_cleanup_plan ----------------------------------------------------------


def _make_project(root):
    files = {
        "metadata.json": "{}",
        "blueprint/blueprint.json": "{}",
        "snapshot/pages/index.html": "x" * 100,
        "snapshot/image/a.png": "x" * 200,
        "generated/pro/index.html": "x" * 50,
        "generated/pro/full/about.html": "x" * 50,
        "generated/premium/index.html": "x" * 70,
        "downloads/pro.zip": "x" * 30,
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_apply_deletes_only_planned_paths(tmp_path):
    _make_project(tmp_path)
    plan = CleanupPlan(tier_dirs_to_delete=("premium",), delete_snapshot=True)

    freed = apply_cleanup_plan(tmp_path, plan)

    assert freed == 70 + 300 + 30
    assert not (tmp_path / "generated/premium").exists()
    assert not (tmp_path / "snapshot").exists()
    assert not (tmp_path / "downloads").exists()
    # Kept: the purchased tier (incl. its full-site build), blueprint, metadata.
    assert (tmp_path / "generated/pro/full/about.html").exists()
    assert (tmp_path / "blueprint/blueprint.json").exists()
    assert (tmp_path / "metadata.json").exists()


def test_apply_keeps_snapshot_when_plan_says_so(tmp_path):
    _make_project(tmp_path)
    apply_cleanup_plan(tmp_path, CleanupPlan(tier_dirs_to_delete=(), delete_snapshot=False))
    assert (tmp_path / "snapshot/image/a.png").exists()


def test_dry_run_reports_size_but_deletes_nothing(tmp_path):
    _make_project(tmp_path)
    plan = CleanupPlan(tier_dirs_to_delete=("premium", "pro"), delete_snapshot=True)

    freed = apply_cleanup_plan(tmp_path, plan, dry_run=True)

    assert freed == 70 + 100 + 300 + 30
    assert (tmp_path / "generated/premium/index.html").exists()
    assert (tmp_path / "snapshot/image/a.png").exists()


def test_apply_is_idempotent_on_already_cleaned_project(tmp_path):
    _make_project(tmp_path)
    plan = CleanupPlan(tier_dirs_to_delete=("premium",), delete_snapshot=True)
    apply_cleanup_plan(tmp_path, plan)
    assert apply_cleanup_plan(tmp_path, plan) == 0


def test_apply_refuses_tier_names_that_escape_generated(tmp_path):
    _make_project(tmp_path)
    plan = CleanupPlan(tier_dirs_to_delete=("..", "../snapshot"), delete_snapshot=False, delete_downloads=False)

    assert apply_cleanup_plan(tmp_path, plan) == 0
    assert (tmp_path / "snapshot").exists()
    assert (tmp_path / "generated").exists()
