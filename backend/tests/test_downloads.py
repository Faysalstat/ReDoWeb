import types

from app.routers.downloads import _resolve_download_plan


def _job(status: str):
    return types.SimpleNamespace(overall_status=status, id="job-id")


def test_resolve_download_plan_single_page_is_always_fast_path():
    assert _resolve_download_plan(1, None) == "fast_path"
    assert _resolve_download_plan(1, _job("running")) == "fast_path"
    assert _resolve_download_plan(0, None) == "fast_path"


def test_resolve_download_plan_multi_page_no_job_yet_starts_a_build():
    assert _resolve_download_plan(3, None) == "start_build"


def test_resolve_download_plan_multi_page_job_running_does_not_duplicate():
    assert _resolve_download_plan(3, _job("running")) == "already_building"


def test_resolve_download_plan_multi_page_job_succeeded_is_fast_path():
    assert _resolve_download_plan(3, _job("succeeded")) == "fast_path"


def test_resolve_download_plan_multi_page_job_failed_allows_retry():
    assert _resolve_download_plan(3, _job("failed")) == "start_build"
