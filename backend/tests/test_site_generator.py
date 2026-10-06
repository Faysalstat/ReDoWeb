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


def test_missing_required_output_files_respects_injected_required_files(tmp_path):
    """generate_full_site()'s batches check a per-batch page list, not the
    module-level REQUIRED_OUTPUT_FILES constant generate_site() uses."""
    output_dir = tmp_path / "generated" / "pro" / "full"
    output_dir.mkdir(parents=True)
    (output_dir / "page-1.html").write_text("<html></html>", encoding="utf-8")
    trace_path = output_dir / "_debug_trace.json"

    missing = _missing_required_output_files(
        trace_path, required_files=("page-1.html", "page-2.html", "style.css")
    )

    assert set(missing) == {"page-2.html", "style.css"}


# --- _page_output_filename -------------------------------------------------


def test_page_output_filename_home_page_is_index_html():
    assert site_generator._page_output_filename(0, "https://example.com/") == "index.html"


def test_page_output_filename_other_pages_use_url_slug():
    assert site_generator._page_output_filename(1, "https://example.com/about") == "about.html"
    assert site_generator._page_output_filename(4, "https://example.com/contact-us/") == "contact-us.html"
    assert site_generator._page_output_filename(2, "https://example.com/services/web-design") == "services-web-design.html"
    assert site_generator._page_output_filename(3, "https://example.com/About%20Us.php") == "about-us.html"


def test_page_output_filename_falls_back_to_position_name_when_no_usable_slug():
    assert site_generator._page_output_filename(1, "https://example.com/?page_id=12") == "page-1.html"
    assert site_generator._page_output_filename(2, "https://example.com/index.html") == "page-2.html"
    assert site_generator._page_output_filename(3, "https://example.com/%20/--/") == "page-3.html"


def test_page_output_filename_never_emits_path_traversal_or_unsafe_chars():
    name = site_generator._page_output_filename(1, "https://example.com/../../etc/passwd")
    assert name == "etc-passwd.html"
    assert "/" not in name and "\\" not in name


def test_page_output_filenames_disambiguates_collisions_in_crawl_order():
    names = site_generator._page_output_filenames(
        [
            "https://example.com/",
            "https://example.com/about/",
            "https://example.com/about",
            "https://example.com/ABOUT.html",
        ]
    )
    assert names == ["index.html", "about.html", "about-2.html", "about-3.html"]


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


def test_select_template_with_candidates_restricts_random_choice(monkeypatch):
    """The admin-enabled subset (candidate_templates from
    prompt_template_service.get_active_template_filenames) must be the only
    thing random.choice ever sees -- this is what makes an admin-disabled
    template actually stop being picked."""
    captured = {}

    def fake_choice(seq):
        captured["seq"] = list(seq)
        return seq[0]

    monkeypatch.setattr(site_generator.random, "choice", fake_choice)
    all_templates = sorted(p.name for p in site_generator.PROMPTS_DIR.glob("*.txt"))
    subset = all_templates[:2]

    result = site_generator._select_template(candidates=subset)

    assert {p.name for p in captured["seq"]} == set(subset)
    assert result.name in subset


def test_select_template_candidates_none_preserves_every_file_behavior(monkeypatch):
    """Regression: omitting candidates must behave exactly as it did before
    this admin control existed -- every file on disk is a candidate."""
    captured = {}

    def fake_choice(seq):
        captured["seq"] = list(seq)
        return seq[0]

    monkeypatch.setattr(site_generator.random, "choice", fake_choice)
    all_templates = sorted(p.name for p in site_generator.PROMPTS_DIR.glob("*.txt"))

    site_generator._select_template()

    assert {p.name for p in captured["seq"]} == set(all_templates)


def test_select_template_empty_candidates_raises():
    with pytest.raises(GenerationError):
        site_generator._select_template(candidates=[])


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


# --- generate_full_site: batching, style-continuity pre-copy --------------


def _make_multi_page_project(tmp_path, num_pages: int):
    project_root = tmp_path / "project"
    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True)
    preview_dir = project_root / "generated" / "pro"
    preview_dir.mkdir(parents=True)
    (preview_dir / "index.html").write_text("<html>home</html>", encoding="utf-8")
    (preview_dir / "style.css").write_text("body{color:red}", encoding="utf-8")

    meta = {
        "site_name": "Acme",
        "colors": {"primary": "#111111", "secondary": "#222222", "accent": "#333333"},
        "fonts": {"heading": "Inter", "body": "Inter"},
    }
    pages = [{"page_url": "https://example.com/"}] + [
        {"page_url": f"https://example.com/page-{i}"} for i in range(1, num_pages)
    ]
    (blueprint_dir / "blueprint.json").write_text(
        json.dumps({"meta": meta, "navigation": [], "pages": pages}), encoding="utf-8"
    )
    design_md = (
        "---\n"
        "site_name: Acme\n"
        "colors:\n  primary: '#111111'\n  secondary: '#222222'\n  accent: '#333333'\n"
        "logo: null\n"
        "fonts:\n  heading: Inter\n  body: Inter\n"
        "tone: warm\n"
        "---\n\n## Home Page\n### Hero\nHeadline: Welcome\n"
    )
    (blueprint_dir / "design.md").write_text(design_md, encoding="utf-8")
    (project_root / "metadata.json").write_text(json.dumps({"assets": []}), encoding="utf-8")
    return project_root


def test_generate_full_site_requires_template_override(tmp_path, monkeypatch):
    monkeypatch.setattr(site_generator.tier_service, "is_tier_enabled", lambda key: True)
    project_root = _make_multi_page_project(tmp_path, num_pages=3)

    with pytest.raises(GenerationError):
        site_generator.generate_full_site(project_root, "pro")


def test_generate_full_site_batches_remaining_pages_and_sums_usage(tmp_path, monkeypatch):
    monkeypatch.setattr(site_generator.tier_service, "is_tier_enabled", lambda key: True)
    # 1 home page + 9 remaining -> ceil(9 / FULL_SITE_PAGES_PER_BATCH=4) == 3 batches.
    project_root = _make_multi_page_project(tmp_path, num_pages=10)

    batch_required_files: list[list[str]] = []

    def fake_run_agent_loop(settings, model_name, system_prompt, user_message, dispatch, trace_path=None, required_files=()):
        # Real _run_agent_loop would call dispatch's write_file; here we
        # just materialize the required files directly to isolate the
        # batching/aggregation logic under test from the agent loop itself
        # (already covered by test_run_agent_loop_* above).
        for name in required_files:
            (trace_path.parent / name).write_text("<html></html>", encoding="utf-8")
        batch_required_files.append(list(required_files))
        return "batch done", {"prompt_tokens": 10, "completion_tokens": 5}, 1

    monkeypatch.setattr(site_generator, "_run_agent_loop", fake_run_agent_loop)

    result = site_generator.generate_full_site(project_root, "pro", template_override="business_Industrial_prompt.txt")

    assert len(batch_required_files) == 3
    assert sum(len(batch) for batch in batch_required_files) == 9
    assert result["usage"] == {"prompt_tokens": 30, "completion_tokens": 15}
    assert result["iterations"] == 3
    assert result["template_used"] == "business_Industrial_prompt.txt"


def test_generate_full_site_precopies_preview_files_byte_identical(tmp_path, monkeypatch):
    monkeypatch.setattr(site_generator.tier_service, "is_tier_enabled", lambda key: True)
    project_root = _make_multi_page_project(tmp_path, num_pages=3)

    def fake_run_agent_loop(settings, model_name, system_prompt, user_message, dispatch, trace_path=None, required_files=()):
        for name in required_files:
            (trace_path.parent / name).write_text("<html></html>", encoding="utf-8")
        return "done", {"prompt_tokens": 0, "completion_tokens": 0}, 1

    monkeypatch.setattr(site_generator, "_run_agent_loop", fake_run_agent_loop)

    site_generator.generate_full_site(project_root, "pro", template_override="business_Industrial_prompt.txt")

    full_dir = project_root / "generated" / "pro" / "full"
    assert full_dir.joinpath("index.html").read_text(encoding="utf-8") == "<html>home</html>"
    assert full_dir.joinpath("style.css").read_text(encoding="utf-8") == "body{color:red}"


# --- _run_agent_loop: on_event progress hook ------------------------------


def test_run_agent_loop_emits_iteration_and_tool_events(tmp_path, monkeypatch):
    _stub_two_file_success(monkeypatch)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    events: list[dict] = []

    site_generator._run_agent_loop(
        site_generator.get_settings(),
        "test-model",
        "system",
        "user",
        make_tool_dispatch(output_dir),
        trace_path=output_dir / "_debug_trace.json",
        on_event=events.append,
    )

    assert [e["type"] for e in events] == ["iteration", "tool", "tool", "iteration"]
    tool_events = [e for e in events if e["type"] == "tool"]
    assert [e["args"]["path"] for e in tool_events] == ["index.html", "style.css"]
    assert all(e["ok"] for e in tool_events)


def test_run_agent_loop_survives_a_crashing_on_event_callback(tmp_path, monkeypatch):
    _stub_two_file_success(monkeypatch)
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    def broken(event):
        raise RuntimeError("progress tracking bug")

    summary, _usage, _iterations = site_generator._run_agent_loop(
        site_generator.get_settings(),
        "test-model",
        "system",
        "user",
        make_tool_dispatch(output_dir),
        trace_path=output_dir / "_debug_trace.json",
        on_event=broken,
    )

    assert summary == "Done."
    assert (output_dir / "index.html").exists()
