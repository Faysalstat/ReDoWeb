import pytest
from fastapi import HTTPException

from app.routers.debug_pipeline import _validate_project_id


def test_validate_project_id_accepts_real_uuid():
    _validate_project_id("1eb4f080-e14c-41d7-aa78-968fbc0550be")  # must not raise


def test_validate_project_id_rejects_path_traversal():
    with pytest.raises(HTTPException) as exc_info:
        _validate_project_id("../../../../etc/passwd")
    assert exc_info.value.status_code == 400


def test_validate_project_id_rejects_non_uuid_string():
    with pytest.raises(HTTPException) as exc_info:
        _validate_project_id("not-a-uuid")
    assert exc_info.value.status_code == 400
