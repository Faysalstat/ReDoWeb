import json
from pathlib import Path

import pytest

from app.ai.blueprint_pipeline import run_blueprint_pipeline
from app.ai.blueprint_schema import BlueprintDocument
from app.config import get_settings

HOMEPAGE_HTML = """
<html><head><title>Acme Co - Home</title></head>
<body>
<header><nav><a href="/">Home</a></nav></header>
<main>
<h1>Welcome to Acme Co</h1>
<p>We build great things.</p>
<h2>About Us</h2>
<p>Acme Co was founded in 2010.</p>
</main>
<footer><p>&copy; 2026 Acme Co</p></footer>
</body></html>
"""


@pytest.fixture(autouse=True)
def _no_openrouter_key(monkeypatch):
    """This pipeline test must never make a real network call even if a
    developer's local .env has a real REDOWEBS_OPENROUTER_API_KEY -- forcing
    it empty exercises (and locks in) the graceful-degradation path for
    both review calls, which is itself the behavior worth testing here."""
    monkeypatch.setenv("REDOWEBS_OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    pages_dir = tmp_path / "snapshot" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "index.html").write_text(HOMEPAGE_HTML, encoding="utf-8")

    metadata = {
        "project_id": "test-project",
        "source_url": "https://acme.example.com/",
        "page_count": 1,
        "pages": [
            {
                "url": "https://acme.example.com/",
                "http_status": 200,
                "storage_path": "snapshot/pages/index.html",
            }
        ],
        "assets": [],
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_pipeline_writes_all_three_artifacts(project_root: Path):
    result = run_blueprint_pipeline(project_root)

    assert (project_root / "blueprint" / "scraped.json").exists()
    assert (project_root / "blueprint" / "blueprint.json").exists()
    assert (project_root / "blueprint" / "design.md").exists()
    assert result["scraped_json_path"] == "blueprint/scraped.json"
    assert result["blueprint_json_path"] == "blueprint/blueprint.json"
    assert result["design_md_path"] == "blueprint/design.md"


def test_pipeline_output_validates_against_schema(project_root: Path):
    run_blueprint_pipeline(project_root)

    scraped_data = json.loads((project_root / "blueprint" / "scraped.json").read_text())
    blueprint_data = json.loads((project_root / "blueprint" / "blueprint.json").read_text())

    BlueprintDocument.model_validate(scraped_data)
    BlueprintDocument.model_validate(blueprint_data)


def test_pipeline_degrades_gracefully_without_api_key(project_root: Path):
    """With no OpenRouter key configured, both review calls fail fast and
    the pipeline must still complete -- blueprint.json falls back to the
    heuristically-extracted content rather than raising."""
    result = run_blueprint_pipeline(project_root)

    assert result["blueprint"]["meta"]["site_name"] == "Acme Co"
    assert result["blueprint"]["pages"][0]["sections"]["hero"]["headline"] == "Welcome to Acme Co"
    assert result["usage"] == {"prompt_tokens": 0, "completion_tokens": 0}


def test_pipeline_compat_design_md_has_valid_frontmatter(project_root: Path):
    from app.ai.postprocess import parse_frontmatter

    run_blueprint_pipeline(project_root)
    design_md = (project_root / "blueprint" / "design.md").read_text(encoding="utf-8")

    frontmatter = parse_frontmatter(design_md)
    assert frontmatter["site_name"] == "Acme Co"
    assert set(frontmatter["colors"].keys()) == {"primary", "secondary", "accent"}
