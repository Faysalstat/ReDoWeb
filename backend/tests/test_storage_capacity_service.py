from collections import namedtuple

import pytest

from app.config import get_settings
from app.services.storage_capacity_service import InsufficientDiskSpaceError, check_free_disk_space

_UsageTuple = namedtuple("_UsageTuple", ["total", "used", "free"])


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_check_free_disk_space_passes_when_above_threshold(monkeypatch, tmp_path):
    monkeypatch.setenv("REDOWEBS_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("REDOWEBS_MIN_FREE_DISK_GB", "2")

    ten_gb = 10 * 1024**3
    monkeypatch.setattr(
        "app.services.storage_capacity_service.shutil.disk_usage",
        lambda path: _UsageTuple(total=100 * 1024**3, used=90 * 1024**3, free=ten_gb),
    )

    check_free_disk_space()  # should not raise


def test_check_free_disk_space_raises_when_below_threshold(monkeypatch, tmp_path):
    monkeypatch.setenv("REDOWEBS_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("REDOWEBS_MIN_FREE_DISK_GB", "2")

    half_gb = 512 * 1024**2
    monkeypatch.setattr(
        "app.services.storage_capacity_service.shutil.disk_usage",
        lambda path: _UsageTuple(total=100 * 1024**3, used=99 * 1024**3, free=half_gb),
    )

    with pytest.raises(InsufficientDiskSpaceError):
        check_free_disk_space()
