import types

import pytest

from app.routers.downloads import _resolve_download_plan


def _job(status):
    return types.SimpleNamespace(overall_status=status)


@pytest.mark.parametrize(
    "page_count,job,expected",
    [
        (1, None, "fast_path"),
        (1, _job("failed"), "fast_path"),
        (6, None, "start_build"),
        (6, _job("running"), "already_building"),
        (6, _job("succeeded"), "fast_path"),
        (6, _job("failed"), "start_build"),
    ],
)
def test_resolve_download_plan(page_count, job, expected):
    assert _resolve_download_plan(page_count, job) == expected
