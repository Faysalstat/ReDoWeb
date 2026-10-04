import json

import pytest

from app.ai import blueprint_review
from app.ai.blueprint_review import (
    _extract_visible_text,
    _merge_content_review,
    _merge_gap_sections,
    _review_page_gaps,
    _verify_quote_in_text,
)
from app.ai.blueprint_schema import (
    AboutSection,
    AdditionalSection,
    BlueprintDocument,
    ColorPalette,
    FaqItem,
    Fonts,
    HeroSection,
    MetaBlock,
    PageBlueprint,
    PageSections,
    ServiceItem,
    TestimonialItem,
)
from app.ai.errors import OpenRouterError


def _make_original() -> PageSections:
    return PageSections(
        hero=HeroSection(headline="Old Headline", background_image="snapshot/image/real-hero.jpg"),
        about=AboutSection(heading="About", body="Real facts only.", image="snapshot/image/real-about.jpg"),
        testimonials=[TestimonialItem(quote="Real quote", author="Real Author")],
        additional_sections=[
            AdditionalSection(key="our-coverage-map", title="Our Coverage Map", body="We serve Orlando.", images=["snapshot/image/map.jpg"])
        ],
    )


def test_merge_never_overwrites_image_fields_from_model_response():
    original = _make_original()
    smuggled_result = {
        "hero": {"headline": "New Headline", "background_image": "snapshot/image/fabricated.jpg"},
        "about": {"heading": "About", "body": "Rewritten.", "image": "snapshot/image/fabricated-about.jpg"},
    }

    merged = _merge_content_review(original, smuggled_result)

    assert merged.hero.headline == "New Headline"  # text IS allowed to change
    assert merged.hero.background_image == "snapshot/image/real-hero.jpg"  # image is not
    assert merged.about.image == "snapshot/image/real-about.jpg"


def test_merge_never_reads_optional_no_fabrication_sections_from_response():
    original = _make_original()
    smuggled_result = {
        "hero": {"headline": "New Headline"},
        "testimonials": [{"quote": "Fabricated quote", "author": "Fabricated Author"}],
        "pricing": [{"plan": "Fabricated Plan", "price": "$99"}],
        "contact": {"email": "fabricated@example.com"},
    }

    merged = _merge_content_review(original, smuggled_result)

    assert merged.testimonials == original.testimonials
    assert merged.pricing == []
    assert merged.contact.email == ""


def test_merge_falls_back_to_original_text_when_response_field_is_empty():
    original = _make_original()

    merged = _merge_content_review(original, {})

    assert merged.hero.headline == "Old Headline"
    assert merged.about.body == "Real facts only."


def test_merge_rewrites_existing_additional_section_but_keeps_original_images():
    original = _make_original()
    result = {
        "additional_sections": [
            {"key": "our-coverage-map", "title": "Our Coverage Map", "body": "We proudly serve the Orlando metro area.", "items": []}
        ]
    }

    merged = _merge_content_review(original, result)

    assert len(merged.additional_sections) == 1
    assert merged.additional_sections[0].body == "We proudly serve the Orlando metro area."
    assert merged.additional_sections[0].images == ["snapshot/image/map.jpg"]


def test_merge_matches_service_icons_by_title_not_position_when_consolidated():
    original = _make_original()
    original.services_features = [
        ServiceItem(title="Credit Repair", description="...", icon_image="snapshot/image/credit.png"),
        ServiceItem(title="Sculpting Success", description="...", icon_image="snapshot/image/sculpt.png"),
        ServiceItem(title="Tax Planning", description="...", icon_image="snapshot/image/tax.png"),
    ]
    # Model consolidates 3 -> 2, dropping "Sculpting Success" entirely and
    # reordering -- a naive positional pairing would give "Tax Planning"
    # (now at index 0) the credit.png icon instead of tax.png.
    result = {
        "services_features": [
            {"title": "Tax Planning", "description": "Rewritten tax description."},
            {"title": "Credit Repair", "description": "Rewritten credit description."},
        ]
    }

    merged = _merge_content_review(original, result)

    by_title = {item.title: item.icon_image for item in merged.services_features}
    assert by_title == {"Tax Planning": "snapshot/image/tax.png", "Credit Repair": "snapshot/image/credit.png"}


def test_merge_accepts_deliberate_empty_list_as_drop_everything_not_as_no_response():
    """An empty list is the model's explicit "everything here was
    redundant, keep none of it" signal (the prompt allows consolidating
    services_features/faq/additional_sections down to nothing) -- it must
    not be treated the same as the key being absent, which would silently
    keep the stale original items instead."""
    original = _make_original()
    original.services_features = [ServiceItem(title="Old Service", description="...")]
    original.faq = [FaqItem(question="Old question?", answer="Old answer.")]
    result = {"services_features": [], "faq": [], "additional_sections": []}

    merged = _merge_content_review(original, result)

    assert merged.services_features == []
    assert merged.faq == []
    assert merged.additional_sections == []


def test_merge_drops_additional_section_with_invented_key():
    original = _make_original()
    result = {
        "additional_sections": [
            {"key": "our-coverage-map", "title": "Our Coverage Map", "body": "Rewritten.", "items": []},
            {"key": "fabricated-section", "title": "Made Up Section", "body": "Invented content.", "items": []},
        ]
    }

    merged = _merge_content_review(original, result)

    keys = {section.key for section in merged.additional_sections}
    assert keys == {"our-coverage-map"}


# --- Call C: completeness gap-check -----------------------------------------

SAMPLE_PAGE_HTML = """
<html><head><style>.x{color:red}</style><script>var x=1;</script></head>
<body>
<header><p>Open 9am-5pm Monday to Friday</p></header>
<main><h1>Welcome</h1><p>We build great things.</p></main>
<footer><p>All rights reserved 2026 Acme Co</p></footer>
</body></html>
"""


def test_extract_visible_text_strips_script_and_style():
    text = _extract_visible_text(SAMPLE_PAGE_HTML)

    assert "color:red" not in text
    assert "var x=1" not in text


def test_extract_visible_text_includes_header_and_footer_content():
    """The regression lock for the motivating gap: extraction's
    main-scoped segmentation would miss header/footer text entirely --
    Call C's whole-document scan must not."""
    text = _extract_visible_text(SAMPLE_PAGE_HTML)

    assert "Open 9am-5pm Monday to Friday" in text
    assert "All rights reserved 2026 Acme Co" in text


def test_verify_quote_in_text_accepts_exact_normalized_substring():
    page_text = " ".join("We   proudly    serve the greater Orlando area with pride.".split())

    assert _verify_quote_in_text("We proudly serve the greater Orlando area", page_text)


def test_verify_quote_in_text_rejects_quote_not_present():
    page_text = "We proudly serve the greater Orlando area with pride."

    assert not _verify_quote_in_text("We offer a 100% money-back guarantee", page_text)


def test_verify_quote_in_text_rejects_too_short_quote():
    page_text = "We proudly serve the greater Orlando area with pride."

    assert not _verify_quote_in_text("We", page_text)


@pytest.fixture
def project_root(tmp_path):
    pages_dir = tmp_path / "snapshot" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "index.html").write_text(SAMPLE_PAGE_HTML, encoding="utf-8")
    metadata = {"pages": [{"url": "https://example.com/", "storage_path": "snapshot/pages/index.html"}]}
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_review_page_gaps_adds_verified_quote(project_root, monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths, model=None):
        return (
            {"gaps": [{"quote": "Open 9am-5pm Monday to Friday", "title": "Business Hours", "category": "hours"}]},
            {"prompt_tokens": 10, "completion_tokens": 5},
        )

    monkeypatch.setattr(blueprint_review, "vision_json_chat", fake_vision_json_chat)

    verified, usage = _review_page_gaps(project_root, "snapshot/pages/index.html", PageSections(), [])

    assert len(verified) == 1
    assert verified[0].body == "Open 9am-5pm Monday to Friday"
    assert verified[0].key.startswith("gap-")
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5}


def test_review_page_gaps_drops_response_with_unverifiable_quote(project_root, monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths, model=None):
        return (
            {"gaps": [{"quote": "This exact sentence does not appear anywhere on the page", "title": "Fake", "category": "x"}]},
            {},
        )

    monkeypatch.setattr(blueprint_review, "vision_json_chat", fake_vision_json_chat)

    verified, _usage = _review_page_gaps(project_root, "snapshot/pages/index.html", PageSections(), [])

    assert verified == []


def test_review_page_gaps_ignores_category_that_names_an_optional_section(project_root, monkeypatch):
    """Even if the model's free-text `category` guess names an existing
    Optional section (e.g. "testimonial"), the return type is structurally
    always AdditionalSection -- it can never write into
    sections.testimonials or any other named section."""

    def fake_vision_json_chat(system_prompt, user_text, image_paths, model=None):
        return (
            {"gaps": [{"quote": "Open 9am-5pm Monday to Friday", "title": "Hours", "category": "testimonial"}]},
            {},
        )

    monkeypatch.setattr(blueprint_review, "vision_json_chat", fake_vision_json_chat)

    verified, _usage = _review_page_gaps(project_root, "snapshot/pages/index.html", PageSections(), [])

    assert len(verified) == 1
    assert isinstance(verified[0], AdditionalSection)


def test_review_page_gaps_degrades_to_empty_on_openrouter_error(project_root, monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths, model=None):
        raise OpenRouterError("boom")

    monkeypatch.setattr(blueprint_review, "vision_json_chat", fake_vision_json_chat)

    verified, usage = _review_page_gaps(project_root, "snapshot/pages/index.html", PageSections(), [])

    assert verified == []
    assert usage == {}


def test_review_page_gaps_degrades_on_missing_storage_path(project_root):
    verified, usage = _review_page_gaps(project_root, None, PageSections(), [])

    assert verified == []
    assert usage == {}


def test_review_page_gaps_degrades_on_malformed_gaps_shape(project_root, monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths, model=None):
        return {"gaps": "not-a-list"}, {}

    monkeypatch.setattr(blueprint_review, "vision_json_chat", fake_vision_json_chat)

    verified, _usage = _review_page_gaps(project_root, "snapshot/pages/index.html", PageSections(), [])

    assert verified == []


def test_merge_gap_sections_appends_without_touching_existing_entries():
    existing = [AdditionalSection(key="a", title="A", body="body a")]
    new_gaps = [AdditionalSection(key="gap-b", title="B", body="body b")]

    merged = _merge_gap_sections(existing, new_gaps)

    assert [s.key for s in merged] == ["a", "gap-b"]
    assert existing == [AdditionalSection(key="a", title="A", body="body a")]


# --- review_blueprint(): page_indices/include_meta scoping ------------------


def _make_scraped_document(num_pages: int) -> BlueprintDocument:
    meta = MetaBlock(
        site_name="Acme",
        colors=ColorPalette(primary="#111111", secondary="#222222", accent="#333333"),
        fonts=Fonts(heading="Inter", body="Inter"),
    )
    urls = ["https://example.com/"] + [f"https://example.com/page-{i}" for i in range(1, num_pages)]
    pages = [PageBlueprint(page_url=url, sections=PageSections()) for url in urls]
    return BlueprintDocument(meta=meta, navigation=[], pages=pages)


@pytest.fixture
def multi_page_project_root(tmp_path):
    pages_dir = tmp_path / "snapshot" / "pages"
    pages_dir.mkdir(parents=True)
    urls = ["https://example.com/", "https://example.com/page-1", "https://example.com/page-2"]
    pages_meta = []
    for index, url in enumerate(urls):
        slug = "index" if index == 0 else f"page-{index}"
        (pages_dir / f"{slug}.html").write_text(SAMPLE_PAGE_HTML, encoding="utf-8")
        pages_meta.append({"url": url, "storage_path": f"snapshot/pages/{slug}.html"})
    (tmp_path / "metadata.json").write_text(json.dumps({"pages": pages_meta}), encoding="utf-8")
    return tmp_path


def _fake_vision_json_chat_recording(calls: list):
    def fake(system_prompt, user_text, image_paths, model=None):
        calls.append(system_prompt)
        if system_prompt == blueprint_review.META_REVIEW_SYSTEM_PROMPT:
            return {"site_name": "Acme Reviewed"}, {"prompt_tokens": 1, "completion_tokens": 1}
        if system_prompt == blueprint_review.CONTENT_REVIEW_SYSTEM_PROMPT:
            return {}, {"prompt_tokens": 2, "completion_tokens": 2}
        return {"gaps": []}, {"prompt_tokens": 1, "completion_tokens": 1}

    return fake


def test_review_blueprint_page_indices_filters_to_requested_page(multi_page_project_root, monkeypatch):
    scraped = _make_scraped_document(3)
    calls: list = []
    monkeypatch.setattr(blueprint_review, "vision_json_chat", _fake_vision_json_chat_recording(calls))

    reviewed, _usage = blueprint_review.review_blueprint(multi_page_project_root, scraped, page_indices=[0])

    assert len(reviewed.pages) == 1
    assert reviewed.pages[0].page_url == scraped.pages[0].page_url


def test_review_blueprint_page_indices_preserves_order_and_skips_home(multi_page_project_root, monkeypatch):
    scraped = _make_scraped_document(3)
    calls: list = []
    monkeypatch.setattr(blueprint_review, "vision_json_chat", _fake_vision_json_chat_recording(calls))

    reviewed, _usage = blueprint_review.review_blueprint(
        multi_page_project_root, scraped, page_indices=[1, 2], include_meta=False
    )

    assert [p.page_url for p in reviewed.pages] == [scraped.pages[1].page_url, scraped.pages[2].page_url]


def test_review_blueprint_include_meta_false_never_calls_meta_and_leaves_it_untouched(
    multi_page_project_root, monkeypatch
):
    scraped = _make_scraped_document(3)
    calls: list = []
    monkeypatch.setattr(blueprint_review, "vision_json_chat", _fake_vision_json_chat_recording(calls))

    reviewed, _usage = blueprint_review.review_blueprint(
        multi_page_project_root, scraped, page_indices=[1, 2], include_meta=False
    )

    assert blueprint_review.META_REVIEW_SYSTEM_PROMPT not in calls
    assert reviewed.meta.site_name == "Acme"  # untouched -- the "Acme Reviewed" mock response was never applied


def test_review_blueprint_page_indices_none_regression_tests_full_review(multi_page_project_root, monkeypatch):
    """Default behavior (no page_indices given) must stay unchanged: every
    page reviewed, meta called."""
    scraped = _make_scraped_document(3)
    calls: list = []
    monkeypatch.setattr(blueprint_review, "vision_json_chat", _fake_vision_json_chat_recording(calls))

    reviewed, _usage = blueprint_review.review_blueprint(multi_page_project_root, scraped)

    assert len(reviewed.pages) == 3
    assert [p.page_url for p in reviewed.pages] == [p.page_url for p in scraped.pages]
    assert blueprint_review.META_REVIEW_SYSTEM_PROMPT in calls
    assert reviewed.meta.site_name == "Acme Reviewed"


def test_worker_count_scales_with_target_pages_and_include_meta():
    assert blueprint_review._worker_count(1, include_meta=True) == 3  # 1 meta + 2 for the page
    assert blueprint_review._worker_count(1, include_meta=False) == 2
    assert blueprint_review._worker_count(19, include_meta=False) == 16  # capped, not 38
    assert blueprint_review._worker_count(0, include_meta=False) == 1  # never zero (ThreadPoolExecutor requirement)


# --- review_blueprint(): site_category classification -----------------------


def test_build_meta_category_instruction_empty_when_no_categories():
    assert blueprint_review._build_meta_category_instruction(None) == ""
    assert blueprint_review._build_meta_category_instruction([]) == ""


def test_build_meta_category_instruction_lists_given_categories():
    instruction = blueprint_review._build_meta_category_instruction(["business", "portfolio"])

    assert "business, portfolio" in instruction
    assert "site_category" in instruction


def _fake_vision_json_chat_with_category(calls: list, site_category: str | None):
    def fake(system_prompt, user_text, image_paths, model=None):
        calls.append(system_prompt)
        if system_prompt.startswith(blueprint_review.META_REVIEW_SYSTEM_PROMPT):
            response = {"site_name": "Acme Reviewed"}
            if site_category is not None:
                response["site_category"] = site_category
            return response, {"prompt_tokens": 1, "completion_tokens": 1}
        if system_prompt == blueprint_review.CONTENT_REVIEW_SYSTEM_PROMPT:
            return {}, {"prompt_tokens": 2, "completion_tokens": 2}
        return {"gaps": []}, {"prompt_tokens": 1, "completion_tokens": 1}

    return fake


def test_review_blueprint_sets_site_category_from_meta_call(multi_page_project_root, monkeypatch):
    scraped = _make_scraped_document(3)
    calls: list = []
    monkeypatch.setattr(
        blueprint_review, "vision_json_chat", _fake_vision_json_chat_with_category(calls, "portfolio")
    )

    reviewed, _usage = blueprint_review.review_blueprint(
        multi_page_project_root, scraped, available_categories=["business", "portfolio"]
    )

    assert reviewed.meta.site_category == "portfolio"
    # The category list actually reached the model's system prompt.
    assert any("business, portfolio" in call for call in calls)


def test_review_blueprint_site_category_blank_when_meta_omits_it(multi_page_project_root, monkeypatch):
    scraped = _make_scraped_document(3)
    calls: list = []
    monkeypatch.setattr(blueprint_review, "vision_json_chat", _fake_vision_json_chat_with_category(calls, None))

    reviewed, _usage = blueprint_review.review_blueprint(
        multi_page_project_root, scraped, available_categories=["business", "portfolio"]
    )

    assert reviewed.meta.site_category == ""  # scraped.meta.site_category default, never raises


def test_review_blueprint_site_category_untouched_when_include_meta_false(multi_page_project_root, monkeypatch):
    scraped = _make_scraped_document(3)
    scraped.meta.site_category = "business"
    calls: list = []
    monkeypatch.setattr(
        blueprint_review, "vision_json_chat", _fake_vision_json_chat_with_category(calls, "portfolio")
    )

    reviewed, _usage = blueprint_review.review_blueprint(
        multi_page_project_root, scraped, page_indices=[1, 2], include_meta=False
    )

    assert reviewed.meta.site_category == "business"  # unchanged -- meta call never ran


def test_review_blueprint_site_category_degrades_on_openrouter_error(multi_page_project_root, monkeypatch):
    scraped = _make_scraped_document(3)

    def fake(system_prompt, user_text, image_paths, model=None):
        if system_prompt.startswith(blueprint_review.META_REVIEW_SYSTEM_PROMPT):
            raise OpenRouterError("boom")
        if system_prompt == blueprint_review.CONTENT_REVIEW_SYSTEM_PROMPT:
            return {}, {}
        return {"gaps": []}, {}

    monkeypatch.setattr(blueprint_review, "vision_json_chat", fake)

    reviewed, _usage = blueprint_review.review_blueprint(
        multi_page_project_root, scraped, available_categories=["business", "portfolio"]
    )

    assert reviewed.meta.site_category == ""
