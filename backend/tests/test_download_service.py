import zipfile

from app.services import download_service


def _make_output(tmp_path):
    out = tmp_path / "generated" / "pro"
    (out / "images").mkdir(parents=True)
    (out / "index.html").write_text("<html></html>")
    (out / "about.html").write_text("<html></html>")
    (out / "style.css").write_text("body{}")
    (out / "script.js").write_text("")
    (out / "design.md").write_text("# design")
    (out / "sitemap.xml").write_text("<urlset/>")
    (out / "images" / "logo.png").write_bytes(b"png")
    (out / "blueprint.json").write_text("{}")
    (out / "_debug_trace.json").write_text("{}")
    (out / "_debug_trace_batch_2.json").write_text("{}")
    return out


def test_zip_keeps_site_files_and_drops_internal_artifacts(tmp_path):
    out = _make_output(tmp_path)
    archive_path = tmp_path / "pro.zip"

    download_service.write_site_zip(out, archive_path)

    names = set(zipfile.ZipFile(archive_path).namelist())
    assert names == {
        "index.html",
        "about.html",
        "style.css",
        "script.js",
        "design.md",
        "sitemap.xml",
        "images/logo.png",
    }


def test_zip_overwrites_previous_archive_and_leaves_no_temp_files(tmp_path):
    out = _make_output(tmp_path)
    archive_path = tmp_path / "pro.zip"
    archive_path.write_text("stale")

    download_service.write_site_zip(out, archive_path)

    assert zipfile.is_zipfile(archive_path)
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_build_download_zip_writes_into_project_downloads_dir(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("REDOWEBS_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    project_root = tmp_path / "projects" / "p1"
    (project_root / "generated" / "pro").mkdir(parents=True)
    (project_root / "generated" / "pro" / "index.html").write_text("x")

    archive = download_service.build_download_zip("p1", "pro", "generated/pro")

    assert archive == project_root / "downloads" / "pro.zip"
    assert zipfile.ZipFile(archive).namelist() == ["index.html"]
