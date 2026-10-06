"""Regression tests for the 2026-10-06 SEO-run failure: every edit_file
call missed because the page had been re-serialized by BeautifulSoup
(`&amp;`, `content` before `name`, `/>`) while the model wrote `&`,
`name` first, no `/>` -- and read results were compacted out of context,
so it wrote every snippet from memory. Covers the fixes: structured
parser-backed tools, tolerant edit_file matching, path normalization, and
keeping the latest read of each file in context."""

import json

import pytest

from app.ai import site_generator
from app.ai.errors import GenerationError
from app.ai.generation_tools import _resolve_safe_path, make_seo_tool_dispatch, make_tool_dispatch
from app.ai.seo_tools import ALL_SEO_TOOL_SCHEMAS, make_structured_seo_dispatch

# Shaped exactly like the real failing page: BeautifulSoup output.
PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1" name="viewport"/>
<title>Doggy Duty - Professional Pet Waste Management &amp; Valet Trash Services</title>
<meta content="Old description" name="description"/>
</head><body>
<header><nav><a href="index.html">Home</a><a href="/old-services">Services</a></nav></header>
<main>
<h2 class="hero-title">Clean yards, happy pets</h2>
<p>We offer weekly pet waste removal and valet trash services for apartment communities.</p>
<h4>Why us</h4>
<img src="images/dog.jpg"/>
<img alt="x" src="images/truck.jpg"/>
<a href="contact.html"><svg></svg></a>
</main>
</body></html>"""


@pytest.fixture
def site(tmp_path):
    (tmp_path / "index.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "services.html").write_text("<html><body><p>s</p></body></html>", encoding="utf-8")
    return tmp_path


def _read(site, name="index.html"):
    return (site / name).read_text(encoding="utf-8")


# --- tolerant edit_file -------------------------------------------------------


def test_edit_file_matches_the_exact_snippet_that_failed_in_production(site):
    dispatch = make_seo_tool_dispatch(site)

    result = dispatch["edit_file"](
        "index.html",
        "<title>Doggy Duty - Professional Pet Waste Management & Valet Trash Services</title>",
        "<title>Pet Waste Removal & Valet Trash | Doggy Duty</title>",
    )

    assert result == "Edited index.html"
    assert "<title>Pet Waste Removal &amp; Valet Trash | Doggy Duty</title>" in _read(site)


def test_edit_file_tolerates_self_closing_and_whitespace_differences(site):
    dispatch = make_seo_tool_dispatch(site)

    result = dispatch["edit_file"](
        "index.html",
        '<meta charset="utf-8">\n   <meta content="width=device-width, initial-scale=1" name="viewport">',
        '<meta charset="utf-8"/><meta content="width=device-width, initial-scale=1" name="viewport"/>',
    )

    assert result == "Edited index.html"


def test_tolerant_matching_never_matches_different_text(site):
    dispatch = make_seo_tool_dispatch(site)

    result = dispatch["edit_file"]("index.html", "<title>Doggy Duty - Pet Waste</title>", "<title>x</title>")

    assert result.startswith("Error") and "structured tools" in result
    assert _read(site) == PAGE


# --- path normalization ---------------------------------------------------------


def test_leading_slash_means_sandbox_root_not_escape(tmp_path):
    assert _resolve_safe_path(tmp_path, "/") == tmp_path.resolve()
    assert _resolve_safe_path(tmp_path, "/index.html") == (tmp_path / "index.html").resolve()
    with pytest.raises(GenerationError):
        _resolve_safe_path(tmp_path, "/../secret")


def test_list_files_slash_lists_the_site(site):
    assert "index.html" in make_seo_tool_dispatch(site)["list_files"]("/")


def test_locked_file_cannot_be_reached_through_dot_slash_spelling(site):
    """Also protects the full-site build, whose index.html lock used to
    compare the raw path string."""
    original = _read(site)
    dispatch = make_tool_dispatch(site, locked_files={"index.html"})

    assert dispatch["write_file"]("./index.html", "<html>clobbered</html>").startswith("Error")
    assert dispatch["write_file"]("/index.html", "<html>clobbered</html>").startswith("Error")
    assert _read(site) == original


def test_append_only_applies_to_dot_slash_spelling(tmp_path):
    (tmp_path / "style.css").write_text(".a{}", encoding="utf-8")
    dispatch = make_tool_dispatch(tmp_path, append_only_files={"style.css"})

    dispatch["write_file"]("./style.css", ".b{}")

    assert (tmp_path / "style.css").read_text(encoding="utf-8").startswith(".a{}")


# --- structured tools ------------------------------------------------------------


def test_outline_is_compact_and_indexed(site):
    outline = json.loads(make_structured_seo_dispatch(site)["get_page_outline"]("index.html"))

    assert outline["title"].startswith("Doggy Duty - Professional Pet Waste Management & Valet")
    assert outline["meta_description"] == "Old description"
    assert [h["level"] for h in outline["headings"]] == [2, 4]
    assert [i["src"] for i in outline["images"]] == ["images/dog.jpg", "images/truck.jpg"]
    assert outline["images"][0]["alt"] is None
    assert outline["links"][1] == {"index": 1, "href": "/old-services", "text": "Services"}
    assert outline["heading_retag_safe"] is True
    assert len(json.dumps(outline)) < len(PAGE) * 2


def test_set_title_and_description_without_reproducing_markup(site):
    dispatch = make_structured_seo_dispatch(site)

    assert "set" in dispatch["set_title"]("index.html", "Pet Waste Removal & Valet Trash | Doggy Duty")
    assert "set" in dispatch["set_meta_description"]("index.html", "Weekly pet waste removal for apartments.")

    html = _read(site)
    assert "<title>Pet Waste Removal &amp; Valet Trash | Doggy Duty</title>" in html
    assert 'content="Weekly pet waste removal for apartments."' in html
    assert html.count('name="description"') == 1


def test_set_meta_description_adds_tag_when_missing(site):
    dispatch = make_structured_seo_dispatch(site)

    dispatch["set_meta_description"]("services.html", "Our services.")

    assert 'name="description"' in _read(site, "services.html")


def test_set_image_alt_by_index_and_bad_index_is_a_readable_error(site):
    dispatch = make_structured_seo_dispatch(site)

    dispatch["set_image_alt"]("index.html", 0, "Happy dog in a clean yard")
    assert 'alt="Happy dog in a clean yard"' in _read(site)
    assert dispatch["set_image_alt"]("index.html", 9, "x").startswith("Error")


def test_set_heading_level_keeps_classes_and_text(site):
    dispatch = make_structured_seo_dispatch(site)

    dispatch["set_heading_level"]("index.html", 0, 1)
    dispatch["set_heading_level"]("index.html", 1, 2)

    html = _read(site)
    assert '<h1 class="hero-title">Clean yards, happy pets</h1>' in html
    assert "<h2>Why us</h2>" in html


def test_set_heading_level_refused_on_retag_unsafe_page(site):
    dispatch = make_structured_seo_dispatch(site, retag_unsafe_pages={"index.html"})

    result = dispatch["set_heading_level"]("index.html", 0, 1)

    assert result.startswith("Error") and "styled by tag" in result
    assert _read(site) == PAGE


def test_update_link_href_and_text_but_not_text_of_icon_links(site):
    dispatch = make_structured_seo_dispatch(site)

    dispatch["update_link"]("index.html", 1, href="services.html", text="Our services")
    assert '<a href="services.html">Our services</a>' in _read(site)
    assert dispatch["update_link"]("index.html", 2, text="Contact").startswith("Error")


def test_link_phrase_wraps_unique_body_phrase_only(site):
    dispatch = make_structured_seo_dispatch(site)

    result = dispatch["link_phrase"]("index.html", "valet trash services", "services.html")

    assert "Linked" in result
    assert '<a href="services.html">valet trash services</a>' in _read(site)
    # Not in body text (only in the <title>/nav) -> refused.
    assert dispatch["link_phrase"]("index.html", "Professional Pet Waste", "x.html").startswith("Error")


def test_link_phrase_is_capped_per_page(site):
    (site / "index.html").write_text(
        "<html><body><p>alpha beta gamma delta epsilon</p></body></html>", encoding="utf-8"
    )
    dispatch = make_structured_seo_dispatch(site)
    for word in ("alpha", "beta", "gamma"):
        assert "Linked" in dispatch["link_phrase"]("index.html", word, "a.html")

    assert dispatch["link_phrase"]("index.html", "delta", "a.html").startswith("Error")


def test_add_structured_data_validates_and_replaces_same_type(site):
    dispatch = make_structured_seo_dispatch(site)

    assert dispatch["add_structured_data"]("index.html", "{not json").startswith("Error")
    dispatch["add_structured_data"]("index.html", json.dumps({"@type": "Organization", "name": "A"}))
    dispatch["add_structured_data"]("index.html", json.dumps({"@type": "Organization", "name": "B"}))
    dispatch["add_structured_data"]("index.html", json.dumps({"@type": "WebSite", "name": "B"}))

    html = _read(site)
    assert html.count("application/ld+json") == 2
    assert '"name": "B"' in html and '"name": "A"' not in html


def test_structured_tools_respect_sandbox_and_missing_pages(site):
    dispatch = make_structured_seo_dispatch(site)

    assert dispatch["set_title"]("nope.html", "x").startswith("Error")
    with pytest.raises(GenerationError):
        dispatch["set_title"]("../outside.html", "x")


def test_schemas_list_structured_tools_first():
    names = [s["function"]["name"] for s in ALL_SEO_TOOL_SCHEMAS]
    assert names[0] == "get_page_outline"
    assert names.index("set_title") < names.index("edit_file")


# --- compaction: latest read per file stays in context ---------------------------


def _assistant_read(call_id, path, tool="read_file"):
    return {
        "role": "assistant",
        "tool_calls": [{"id": call_id, "function": {"name": tool, "arguments": json.dumps({"path": path})}}],
    }


def _tool_result(call_id, content):
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def test_keep_latest_reads_compacts_only_superseded_reads():
    big = "x" * 1000
    messages = [
        {"role": "system", "content": "s"},
        _assistant_read("a", "index.html"),
        _tool_result("a", big + "old"),
        _assistant_read("b", "./index.html"),
        _tool_result("b", big + "new"),
        _assistant_read("c", "about.html", tool="get_page_outline"),
        _tool_result("c", big + "outline"),
    ]

    site_generator._compact_resolved_tool_turns(messages, len(messages), keep_latest_reads=True)

    assert messages[2]["content"].startswith("(compacted")
    assert messages[4]["content"].endswith("new")
    assert messages[6]["content"].endswith("outline")


def test_default_compaction_behavior_unchanged():
    messages = [_assistant_read("a", "index.html"), _tool_result("a", "y" * 1000)]

    site_generator._compact_resolved_tool_turns(messages, len(messages))

    assert messages[1]["content"].startswith("(compacted")


# --- guessed folder paths (seen: "public/index.html") -----------------------


def test_guessed_folder_path_maps_to_top_level_page_with_a_note(site):
    dispatch = make_structured_seo_dispatch(site)

    result = dispatch["set_title"]("public/index.html", "New | Doggy Duty")

    assert result.startswith("(note: 'public/index.html' doesn't exist -- used 'index.html'")
    assert "<title>New | Doggy Duty</title>" in _read(site)
    assert "Doggy Duty" in dispatch["read_file"]("src/index.html")


def test_unknown_page_error_lists_the_real_pages(site):
    result = make_structured_seo_dispatch(site)["set_title"]("public/nope.html", "x")

    assert result.startswith("Error") and "index.html, services.html" in result
