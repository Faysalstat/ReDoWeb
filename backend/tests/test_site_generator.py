import json
import types

import pytest

from app.ai import site_generator
from app.ai.errors import GenerationError
from app.ai.generation_tools import make_tool_dispatch
from app.ai.site_generator import _missing_required_output_files

# --- _missing_required_output_files --------------------------------------


def test_missing_required_output_files_reports_both_when_neither_exists(tmp_path):
    output_dir = tmp_path / "generated" / "pro"
    output_dir.mkdir(parents=True)
    trace_path = output_dir / "_debug_trace.json"

    assert set(_missing_required_output_files(trace_path)) == {"index.html", "style.css"}


def test_missing_required_output_files_reports_only_the_missing_one(tmp_path):
    output_dir = tmp_path / "generated" / "pro"
    output_dir.mkdir(parents=True)
    (output_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    trace_path = output_dir / "_debug_trace.json"

    assert _missing_required_output_files(trace_path) == ["style.css"]


def test_missing_required_output_files_empty_when_both_exist(tmp_path):
    output_dir = tmp_path / "generated" / "pro"
    output_dir.mkdir(parents=True)
    (output_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (output_dir / "style.css").write_text("body {}", encoding="utf-8")
    trace_path = output_dir / "_debug_trace.json"

    assert _missing_required_output_files(trace_path) == []


def test_missing_required_output_files_never_blocks_when_trace_path_is_none():
    assert _missing_required_output_files(None) == []


# --- _run_agent_loop: premature-stop regression --------------------------
# Locks in a real failure seen end-to-end: one write_file call in an
# iteration succeeded (index.html) while a sibling call in the SAME
# iteration failed (malformed tool-call JSON from the model for style.css).
# Per-iteration failure tracking never triggered a retry (the iteration
# still counted as a success), and the model's next turn falsely claimed
# completion (finish_reason=stop, no more tool_calls) without style.css
# ever having been written.


def _tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _response(finish_reason: str, tool_calls: list | None = None, content: str | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }


def test_run_agent_loop_retries_when_model_claims_done_but_style_css_missing(tmp_path, monkeypatch):
    output_dir = tmp_path / "generated" / "pro"
    output_dir.mkdir(parents=True)
    dispatch = make_tool_dispatch(output_dir)
    trace_path = output_dir / "_debug_trace.json"

    responses = [
        _response(
            "tool_calls",
            tool_calls=[_tool_call("c1", "write_file", {"path": "index.html", "content": "<html></html>"})],
        ),
        _response("stop", content="All done! Created index.html and style.css."),
        _response(
            "tool_calls",
            tool_calls=[_tool_call("c2", "write_file", {"path": "style.css", "content": "body {}"})],
        ),
        _response("stop", content="All done for real this time."),
    ]

    def fake_chat_completion(payload, timeout=180.0):
        return responses.pop(0)

    monkeypatch.setattr(site_generator, "chat_completion", fake_chat_completion)

    settings = types.SimpleNamespace(
        generation_model="test-model",
        generation_max_tokens=1000,
        generation_max_iterations=10,
        generation_max_consecutive_failures=5,
        generation_prompt_caching_enabled=False,
        generation_call_timeout_seconds=180.0,
    )

    summary, _usage, iterations = site_generator._run_agent_loop(
        settings, "test-model", "system prompt", "user message", dispatch, trace_path=trace_path
    )

    assert (output_dir / "index.html").exists()
    assert (output_dir / "style.css").exists()
    assert summary == "All done for real this time."
    assert iterations == 4
    assert responses == []  # every scripted response was actually consumed


def test_run_agent_loop_aborts_if_required_file_never_gets_written(tmp_path, monkeypatch):
    output_dir = tmp_path / "generated" / "pro"
    output_dir.mkdir(parents=True)
    dispatch = make_tool_dispatch(output_dir)
    trace_path = output_dir / "_debug_trace.json"

    def fake_chat_completion(payload, timeout=180.0):
        # Always claims done, never writes style.css -- must not loop forever.
        return _response("stop", content="Done (but never actually wrote style.css).")

    monkeypatch.setattr(site_generator, "chat_completion", fake_chat_completion)

    settings = types.SimpleNamespace(
        generation_model="test-model",
        generation_max_tokens=1000,
        generation_max_iterations=10,
        generation_max_consecutive_failures=3,
        generation_prompt_caching_enabled=False,
        generation_call_timeout_seconds=180.0,
    )
    (output_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    with pytest.raises(GenerationError):
        site_generator._run_agent_loop(
            settings, "test-model", "system prompt", "user message", dispatch, trace_path=trace_path
        )


# --- _select_template (template-based strategy) ---------------------------


def test_select_template_with_override_returns_that_exact_file():
    path = site_generator._select_template("business_Industrial_prompt.txt")

    assert path.name == "business_Industrial_prompt.txt"
    assert path.exists()


def test_select_template_override_raises_for_unknown_file():
    with pytest.raises(GenerationError):
        site_generator._select_template("not_a_real_template.txt")


def test_select_template_override_rejects_path_traversal():
    with pytest.raises(GenerationError):
        site_generator._select_template("../../../../../../etc/passwd")


def test_select_template_without_override_picks_a_real_template():
    path = site_generator._select_template()

    assert path.exists()
    assert path.suffix == ".txt"


# --- generate_site: every tier uses the template-based strategy -----------


def _make_project(tmp_path, colors=None, fonts=None, tone="warm and friendly") -> "Path":
    from pathlib import Path

    project_root: Path = tmp_path / "project"
    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True)

    colors = colors or {"primary": "#111111", "secondary": "#222222", "accent": "#333333"}
    fonts = fonts or {"heading": "Inter Tight", "body": "Inter"}
    design_md = (
        "---\n"
        "site_name: Acme Co\n"
        f"colors:\n  primary: '{colors['primary']}'\n  secondary: '{colors['secondary']}'\n  accent: '{colors['accent']}'\n"
        "logo: null\n"
        f"fonts:\n  heading: {fonts['heading']}\n  body: {fonts['body']}\n"
        f"tone: {tone}\n"
        "---\n\n## Home Page\n### Hero\nHeadline: Welcome\n"
    )
    (blueprint_dir / "design.md").write_text(design_md, encoding="utf-8")
    (project_root / "metadata.json").write_text(json.dumps({"assets": []}), encoding="utf-8")
    return project_root


def _stub_two_file_success(monkeypatch):
    """Minimal chat_completion stub: writes both required files in one
    iteration, then reports done -- matches the real, minimal successful
    path already covered by test_run_agent_loop_retries_when_model_claims_done..."""
    responses = [
        _response(
            "tool_calls",
            tool_calls=[
                _tool_call("c1", "write_file", {"path": "index.html", "content": "<html></html>"}),
                _tool_call("c2", "write_file", {"path": "style.css", "content": "body {}"}),
            ],
        ),
        _response("stop", content="Done."),
    ]

    def fake_chat_completion(payload, timeout=180.0):
        return responses.pop(0)

    monkeypatch.setattr(site_generator, "chat_completion", fake_chat_completion)
    return responses


@pytest.mark.parametrize("tier_key", ["premium", "pro"])
def test_generate_site_uses_template_strategy_for_every_tier(tmp_path, monkeypatch, tier_key):
    monkeypatch.setattr(site_generator.tier_service, "is_tier_enabled", lambda key: True)
    responses = _stub_two_file_success(monkeypatch)
    project_root = _make_project(tmp_path)

    result = site_generator.generate_site(project_root, tier_key)

    assert result["template_used"].endswith(".txt")
    output_dir = project_root / "generated" / tier_key
    assert not (output_dir / "design_system.json").exists()
    assert responses == []
