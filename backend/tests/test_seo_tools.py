"""SEO pass tool sandbox (generation_tools.make_seo_tool_dispatch): the
agent edits a finished, paid-for site, so it may only change existing
pages via exact, unique snippet replacement -- never rewrite them."""

import pytest

from app.ai.errors import GenerationError
from app.ai.generation_tools import SEO_TOOL_SCHEMAS, make_seo_tool_dispatch


def test_seo_tool_schemas_expose_edit_file():
    names = [schema["function"]["name"] for schema in SEO_TOOL_SCHEMAS]
    assert names == ["write_file", "edit_file", "read_file", "list_files"]


def test_edit_file_replaces_exactly_one_unique_match(tmp_path):
    (tmp_path / "index.html").write_text("<title>Old</title><p>x</p>", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(tmp_path)

    result = dispatch["edit_file"]("index.html", "<title>Old</title>", "<title>New | Acme</title>")

    assert result.startswith("Edited")
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<title>New | Acme</title><p>x</p>"


def test_edit_file_rejects_missing_match_without_changing_file(tmp_path):
    (tmp_path / "index.html").write_text("<p>x</p>", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(tmp_path)

    result = dispatch["edit_file"]("index.html", "<p>nope</p>", "<p>y</p>")

    assert "not found" in result
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<p>x</p>"


def test_edit_file_rejects_ambiguous_match(tmp_path):
    (tmp_path / "index.html").write_text("<p>x</p><p>x</p>", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(tmp_path)

    result = dispatch["edit_file"]("index.html", "<p>x</p>", "<p>y</p>")

    assert "2 times" in result
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<p>x</p><p>x</p>"


def test_edit_file_rejects_empty_old_string_and_missing_file(tmp_path):
    (tmp_path / "index.html").write_text("<p>x</p>", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(tmp_path)

    assert dispatch["edit_file"]("index.html", "", "y").startswith("Error")
    assert dispatch["edit_file"]("missing.html", "a", "b").startswith("Error")


def test_edit_file_blocks_path_traversal(tmp_path):
    sandbox = tmp_path / "seo"
    sandbox.mkdir()
    (tmp_path / "secret.html").write_text("<p>x</p>", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(sandbox)

    with pytest.raises(GenerationError):
        dispatch["edit_file"]("../secret.html", "<p>x</p>", "<p>pwned</p>")
    assert (tmp_path / "secret.html").read_text(encoding="utf-8") == "<p>x</p>"


def test_edit_file_respects_locked_files(tmp_path):
    (tmp_path / "index.html").write_text("<p>x</p>", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(tmp_path, locked_files={"index.html"})

    assert "locked" in dispatch["edit_file"]("index.html", "<p>x</p>", "<p>y</p>")
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<p>x</p>"


@pytest.mark.parametrize("name", ["index.html", "style.css", "script.js"])
def test_write_file_cannot_overwrite_existing_site_files(tmp_path, name):
    (tmp_path / name).write_text("original", encoding="utf-8")
    dispatch = make_seo_tool_dispatch(tmp_path)

    result = dispatch["write_file"](name, "replaced")

    assert result.startswith("Error")
    assert (tmp_path / name).read_text(encoding="utf-8") == "original"


def test_write_file_can_create_a_new_file(tmp_path):
    dispatch = make_seo_tool_dispatch(tmp_path)

    dispatch["write_file"]("humans.txt", "Team: Acme")

    assert (tmp_path / "humans.txt").read_text(encoding="utf-8") == "Team: Acme"
