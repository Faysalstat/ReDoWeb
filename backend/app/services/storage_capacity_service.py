import shutil
from pathlib import Path

from ..config import get_settings

_BYTES_PER_GB = 1024**3


class InsufficientDiskSpaceError(Exception):
    """Raised when free space on the storage volume is below the configured
    minimum."""


def check_free_disk_space() -> None:
    """Raises InsufficientDiskSpaceError if the storage_root volume has less
    than `min_free_disk_gb` free. Cheap (a single shutil.disk_usage
    syscall) -- called at submission (before any credit is spent) and again
    defensively at the start of each pipeline task, since other concurrent
    projects may have consumed space between submission and this job
    actually running."""
    settings = get_settings()
    storage_root = Path(settings.storage_root)
    storage_root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(storage_root).free
    min_free_bytes = settings.min_free_disk_gb * _BYTES_PER_GB
    if free_bytes < min_free_bytes:
        raise InsufficientDiskSpaceError(
            f"Only {free_bytes / _BYTES_PER_GB:.1f}GB free on the storage volume, "
            f"need at least {settings.min_free_disk_gb}GB"
        )
