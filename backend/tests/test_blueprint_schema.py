from app.ai.blueprint_schema import (
    BlueprintDocument,
    ColorPalette,
    Fonts,
    MetaBlock,
    PageBlueprint,
    PageSections,
)

ALL_SECTION_KEYS = {
    "hero", "about", "services_features", "faq", "cta_section", "footer",
    "testimonials", "gallery_portfolio", "team", "pricing",
    "stats_social_proof", "credentials_awards", "contact", "blog_news",
    "additional_sections",
}


def test_fresh_page_sections_serializes_all_known_keys():
    dumped = PageSections().model_dump()
    assert set(dumped.keys()) == ALL_SECTION_KEYS


def _make_document() -> BlueprintDocument:
    return BlueprintDocument(
        meta=MetaBlock(
            site_name="Test Co",
            colors=ColorPalette(primary="#111111", secondary="#eeeeee", accent="#ff0000"),
            fonts=Fonts(heading="Inter", body="Inter"),
        ),
        pages=[PageBlueprint(page_url="https://example.com/")],
    )


def test_blueprint_document_round_trips_through_json():
    original = _make_document()
    dumped = original.model_dump(mode="json")
    restored = BlueprintDocument.model_validate(dumped)
    assert restored == original


def test_round_trip_preserves_all_section_keys_per_page():
    original = _make_document()
    dumped = original.model_dump(mode="json")
    page_sections_keys = set(dumped["pages"][0]["sections"].keys())
    assert page_sections_keys == ALL_SECTION_KEYS
