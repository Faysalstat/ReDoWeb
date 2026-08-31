import pytest

from app.ai.errors import GenerationError
from app.ai.site_generator import _select_template


def test_select_template_with_override_returns_that_exact_file():
    path = _select_template("business_Industrial_prompt.txt")

    assert path.name == "business_Industrial_prompt.txt"
    assert path.exists()


def test_select_template_override_raises_for_unknown_file():
    with pytest.raises(GenerationError):
        _select_template("not_a_real_template.txt")


def test_select_template_override_rejects_path_traversal():
    with pytest.raises(GenerationError):
        _select_template("../../../../../../etc/passwd")


def test_select_template_without_override_picks_a_real_template():
    path = _select_template()

    assert path.exists()
    assert path.suffix == ".txt"
