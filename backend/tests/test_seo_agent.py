"""run_seo_pass wiring with a fake agent loop: the code-enforced backstops
around what the agent did, not the agent's judgment."""

from PIL import Image

from app.ai import seo_agent
from app.ai.blueprint_schema import BlueprintDocument

BLUEPRINT = BlueprintDocument.model_validate(
    {
        "meta": {
            "site_name": "Acme",
            "colors": {"primary": "#111111", "secondary": "#ffffff", "accent": "#333333"},
            "fonts": {"heading": "Inter", "body": "Inter"},
        },
        "pages": [{"page_url": "https://example.com/"}],
    }
)


def _site(tmp_path, css):
    (tmp_path / "images").mkdir()
    Image.new("RGB", (10, 10)).save(tmp_path / "images" / "a.png")
    (tmp_path / "style.css").write_text(css, encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<html><head><title>Acme</title><link rel="stylesheet" href="style.css"></head>'
        "<body><main><h2>Welcome</h2><p>Hi</p></main></body></html>",
        encoding="utf-8",
    )
    return tmp_path


def _fake_agent(monkeypatch, seen):
    def fake_run_agent_loop(
        settings, model_name, system_prompt, user_message, dispatch,
        trace_path=None, required_files=(), tool_schemas=None, on_event=None, keep_latest_reads=False,
        max_iterations=None,
    ):
        seen["max_iterations"] = max_iterations
        assert keep_latest_reads is True  # SEO edits in place, so it must see the current file text
        seen["tools"] = [t["function"]["name"] for t in tool_schemas]
        seen["message"] = user_message
        on_event({"type": "iteration", "iteration": 1, "max_iterations": 10})
        edits = (("<h2>Welcome</h2>", "<h1>Welcome</h1>"), ("<title>Acme</title>", "<title>Welcome | Acme</title>"))
        for old, new in edits:
            args = {"path": "index.html", "old_string": old, "new_string": new}
            result = dispatch["edit_file"](**args)
            on_event(
                {"type": "tool", "iteration": 1, "tool": "edit_file", "args": args,
                 "ok": result.startswith("Edited"), "result": result}
            )
        return "done", {"prompt_tokens": 5, "completion_tokens": 2}, 1

    monkeypatch.setattr(seo_agent, "_run_agent_loop", fake_run_agent_loop)


def test_run_seo_pass_keeps_heading_retag_when_css_is_class_only(tmp_path, monkeypatch):
    seen = {}
    _fake_agent(monkeypatch, seen)
    site = _site(tmp_path, ".hero{color:red}")

    result = seo_agent.run_seo_pass(site, blueprint=BLUEPRINT, site_origin="https://example.com")

    html = (site / "index.html").read_text(encoding="utf-8")
    assert "<h1>Welcome</h1>" in html and "Welcome | Acme" in html
    assert seen["tools"][:2] == ["get_page_outline", "set_title"]  # structured tools first
    assert {"edit_file", "read_file", "list_files", "write_file"} <= set(seen["tools"])
    assert "heading_retag_safe: true" in seen["message"]
    assert result["report"]["pages_restored_heading_changes"] == []
    assert (site / "robots.txt").exists() and (site / "llms.txt").exists()


def test_run_seo_pass_restores_page_when_agent_retags_headings_styled_by_tag(tmp_path, monkeypatch):
    seen = {}
    _fake_agent(monkeypatch, seen)
    site = _site(tmp_path, "h2{font-size:2rem}")

    result = seo_agent.run_seo_pass(site, blueprint=BLUEPRINT, site_origin="https://example.com")

    html = (site / "index.html").read_text(encoding="utf-8")
    assert "<h2>Welcome</h2>" in html  # design-changing retag undone
    assert "heading_retag_safe: false" in seen["message"]
    assert result["report"]["pages_restored_heading_changes"] == ["index.html"]
    # Mechanical fixes still applied after the restore.
    assert 'rel="canonical"' in html


class _RecordingProgress:
    def __init__(self):
        self.steps, self.logs, self.advances = [], [], []

    def start_step(self, key, detail=""):
        self.steps.append(key)

    def advance(self, fraction, detail=None):
        self.advances.append((fraction, detail))

    def log(self, message, level="info"):
        self.logs.append((level, message))


def test_run_seo_pass_reports_steps_and_readable_activity(tmp_path, monkeypatch):
    _fake_agent(monkeypatch, {})
    site = _site(tmp_path, "h2{font-size:2rem}")
    progress = _RecordingProgress()

    result = seo_agent.run_seo_pass(site, blueprint=BLUEPRINT, site_origin="https://example.com", progress=progress)

    assert progress.steps == ["audit", "agent", "checks", "finalize"]
    messages = [m for _, m in progress.logs]
    assert "Edited index.html: headings" in messages
    assert "Edited index.html: page title" in messages
    assert any(level == "warning" and "heading changes undone" in m for level, m in progress.logs)
    assert any(m.startswith("Wrote sitemap.xml") for m in messages)
    assert all(0.0 <= fraction <= 0.95 for fraction, _ in progress.advances)
    assert result["report"]["edits"] == 2 and result["report"]["pages_edited"] == ["index.html"]


def test_describe_edit_labels_common_seo_changes():
    assert seo_agent.describe_edit({"new_string": '<meta name="description" content="x">'}) == "meta description"
    assert seo_agent.describe_edit({"new_string": '<script type="application/ld+json">{}</script>'}) == "structured data"
    assert seo_agent.describe_edit({"new_string": '<img src="a.png" alt="Kitchen">'}) == "image alt text"
    assert seo_agent.describe_edit({"new_string": '<a href="services.html">our services</a>'}) == "links"
    assert seo_agent.describe_edit({"new_string": "plain"}) == "content"


# --- step budget, partial completion, file locations (2026-10-06 run) ------


def test_seo_iteration_budget_scales_with_pages_and_is_capped():
    assert seo_agent.seo_iteration_budget(1) == 16
    assert seo_agent.seo_iteration_budget(5) == 32
    assert seo_agent.seo_iteration_budget(20) == 80
    assert seo_agent.seo_iteration_budget(100) == 80


def test_first_message_states_file_locations_budget_and_embeds_outlines(tmp_path, monkeypatch):
    seen = {}
    _fake_agent(monkeypatch, seen)
    site = _site(tmp_path, ".hero{color:red}")

    seo_agent.run_seo_pass(site, blueprint=BLUEPRINT, site_origin="https://example.com")

    message = seen["message"]
    assert 'TOP LEVEL of your workspace: "index.html"' in message
    assert "no public/" in message
    assert '"headings": [{"index": 0, "level": 2, "text": "Welcome"}]' in message
    assert "at most 16 steps" in message
    assert seen["max_iterations"] == 16


def _agent_that_edits_then_runs_out(monkeypatch, edits: int):
    from app.ai.errors import IterationLimitError

    def fake(settings, model_name, system_prompt, user_message, dispatch, on_event=None, max_iterations=None, **kwargs):
        if edits:
            args = {"path": "public/index.html", "title": "Welcome | Acme"}
            result = dispatch["set_title"](**args)
            on_event({"type": "tool", "iteration": 1, "tool": "set_title", "args": args, "ok": "set" in result, "result": result})
        raise IterationLimitError(
            "Agent did not finish within 16 iterations",
            usage={"prompt_tokens": 9, "completion_tokens": 3},
            iterations=16,
            last_content="partial",
        )

    monkeypatch.setattr(seo_agent, "_run_agent_loop", fake)


def test_running_out_of_steps_keeps_edits_and_still_finalizes(tmp_path, monkeypatch):
    _agent_that_edits_then_runs_out(monkeypatch, edits=1)
    site = _site(tmp_path, ".hero{color:red}")
    progress = _RecordingProgress()

    result = seo_agent.run_seo_pass(site, blueprint=BLUEPRINT, site_origin="https://example.com", progress=progress)

    html = (site / "index.html").read_text(encoding="utf-8")
    assert "<title>Welcome | Acme</title>" in html  # "public/index.html" mapped to index.html
    assert (site / "sitemap.xml").exists()  # finalize still ran
    assert result["report"]["agent_stopped_early"] is True
    assert result["report"]["pages_edited"] == ["index.html"]
    assert result["usage"] == {"prompt_tokens": 9, "completion_tokens": 3}
    assert any(level == "warning" and "step limit" in m for level, m in progress.logs)


def test_running_out_of_steps_with_no_edits_still_fails(tmp_path, monkeypatch):
    import pytest

    from app.ai.errors import IterationLimitError

    _agent_that_edits_then_runs_out(monkeypatch, edits=0)
    site = _site(tmp_path, ".hero{color:red}")

    with pytest.raises(IterationLimitError):
        seo_agent.run_seo_pass(site, blueprint=BLUEPRINT, site_origin="https://example.com")
