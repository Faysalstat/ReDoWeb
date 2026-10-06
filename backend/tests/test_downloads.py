"""Pure decision functions behind Buy -> Download / Generate all pages /
Run SEO (services/tier_actions_service.py). Project uses Postgres-only
column types, so these are tested directly rather than through the router
on SQLite."""

import types

from app.services.tier_actions_service import (
    action_status,
    choose_download_scope,
    resolve_full_site_action,
    resolve_seo_action,
)


def _job(status: str):
    return types.SimpleNamespace(overall_status=status, id="job-id", failure_reason=None)


# --- action_status ------------------------------------------------------------


def test_action_status_maps_missing_job_to_none():
    assert action_status(None) == "none"
    assert action_status(_job("running")) == "running"
    assert action_status(_job("succeeded")) == "succeeded"
    assert action_status(_job("failed")) == "failed"


# --- Generate all pages ---------------------------------------------------------


def test_full_site_not_applicable_for_single_page_site():
    assert resolve_full_site_action(1, None) == "not_applicable"
    assert resolve_full_site_action(0, None) == "not_applicable"


def test_full_site_starts_when_never_run():
    assert resolve_full_site_action(5, None) == "start"


def test_full_site_running_is_not_duplicated():
    assert resolve_full_site_action(5, _job("running")) == "running"


def test_full_site_never_reruns_after_success():
    """User decision 2026-10-05: no rerun of a succeeded build."""
    assert resolve_full_site_action(5, _job("succeeded")) == "already_done"


def test_full_site_retry_allowed_after_failure():
    assert resolve_full_site_action(5, _job("failed")) == "start"


# --- Run SEO agent --------------------------------------------------------------


def test_seo_unavailable_outside_pro_and_premium():
    assert resolve_seo_action("basic", 1, None, None) == "unavailable"


def test_seo_on_multi_page_site_requires_all_pages_generated_first():
    assert resolve_seo_action("pro", 5, None, None) == "needs_full_site"
    assert resolve_seo_action("pro", 5, _job("running"), None) == "needs_full_site"
    assert resolve_seo_action("pro", 5, _job("failed"), None) == "needs_full_site"
    assert resolve_seo_action("pro", 5, _job("succeeded"), None) == "start"


def test_seo_on_single_page_site_is_available_right_after_purchase():
    assert resolve_seo_action("premium", 1, None, None) == "start"


def test_seo_runs_once_retry_only_after_failure():
    assert resolve_seo_action("pro", 1, None, _job("running")) == "running"
    assert resolve_seo_action("pro", 1, None, _job("succeeded")) == "already_done"
    assert resolve_seo_action("pro", 1, None, _job("failed")) == "start"


# --- Download preference --------------------------------------------------------


def test_download_prefers_seo_then_full_site_then_preview():
    seo, full, preview = object(), object(), object()
    assert choose_download_scope(seo, full, preview) is seo
    assert choose_download_scope(None, full, preview) is full
    assert choose_download_scope(None, None, preview) is preview
    assert choose_download_scope(None, None, None) is None
