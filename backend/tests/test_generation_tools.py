from app.ai.generation_tools import make_tool_dispatch


def test_write_file_unrestricted_by_default_still_overwrites(tmp_path):
    """Regression: generate_site()'s existing call site (no locked_files/
    append_only_files passed) must be completely unaffected by the new
    optional params."""
    dispatch = make_tool_dispatch(tmp_path)

    dispatch["write_file"]("index.html", "<html>v1</html>")
    dispatch["write_file"]("index.html", "<html>v2</html>")

    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<html>v2</html>"


def test_write_file_rejects_writes_to_locked_files(tmp_path):
    (tmp_path / "index.html").write_text("<html>original</html>", encoding="utf-8")
    dispatch = make_tool_dispatch(tmp_path, locked_files={"index.html"})

    result = dispatch["write_file"]("index.html", "<html>overwritten</html>")

    assert "cannot be" in result.lower() or "error" in result.lower()
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<html>original</html>"


def test_write_file_locked_file_blocks_even_first_write(tmp_path):
    """Locked isn't just "can't overwrite" -- it must never be creatable
    either, matching generate_full_site()'s use (index.html is pre-copied
    onto disk before the agent loop runs, so a write attempt is always an
    overwrite in practice, but the guard itself shouldn't depend on that)."""
    dispatch = make_tool_dispatch(tmp_path, locked_files={"index.html"})

    dispatch["write_file"]("index.html", "<html>new</html>")

    assert not (tmp_path / "index.html").exists()


def test_write_file_appends_to_append_only_files_instead_of_replacing(tmp_path):
    (tmp_path / "style.css").write_text("body { color: red; }", encoding="utf-8")
    dispatch = make_tool_dispatch(tmp_path, append_only_files={"style.css"})

    result = dispatch["write_file"]("style.css", ".new-class { color: blue; }")

    content = (tmp_path / "style.css").read_text(encoding="utf-8")
    assert "body { color: red; }" in content
    assert ".new-class { color: blue; }" in content
    assert "appended" in result.lower()


def test_write_file_append_only_creates_file_normally_if_it_does_not_exist_yet(tmp_path):
    dispatch = make_tool_dispatch(tmp_path, append_only_files={"style.css"})

    dispatch["write_file"]("style.css", "body { color: red; }")

    assert (tmp_path / "style.css").read_text(encoding="utf-8") == "body { color: red; }"


def test_write_file_paths_outside_locked_or_append_only_sets_write_normally(tmp_path):
    dispatch = make_tool_dispatch(tmp_path, locked_files={"index.html"}, append_only_files={"style.css"})

    dispatch["write_file"]("page-1.html", "<html>page 1</html>")

    assert (tmp_path / "page-1.html").read_text(encoding="utf-8") == "<html>page 1</html>"
