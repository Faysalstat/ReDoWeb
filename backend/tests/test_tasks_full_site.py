from app.ai.blueprint_schema import BlueprintDocument, ColorPalette, Fonts, MetaBlock, PageBlueprint, PageSections
from app.workers.tasks_full_site import _merge_full_blueprint


def _doc(site_name: str, page_urls: list[str]) -> BlueprintDocument:
    meta = MetaBlock(
        site_name=site_name,
        colors=ColorPalette(primary="#111111", secondary="#222222", accent="#333333"),
        fonts=Fonts(heading="Inter", body="Inter"),
    )
    pages = [PageBlueprint(page_url=url, sections=PageSections()) for url in page_urls]
    return BlueprintDocument(meta=meta, navigation=[], pages=pages)


def test_merge_full_blueprint_appends_remaining_pages_after_home_page():
    home = _doc("Acme", ["https://example.com/"])
    remaining = _doc("ignored", ["https://example.com/about", "https://example.com/contact"])

    merged = _merge_full_blueprint(home, remaining)

    assert [p.page_url for p in merged.pages] == [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/contact",
    ]


def test_merge_full_blueprint_keeps_home_blueprints_meta_not_remainings():
    home = _doc("Acme (already reviewed)", ["https://example.com/"])
    remaining = _doc("untouched copy, should be ignored", ["https://example.com/about"])

    merged = _merge_full_blueprint(home, remaining)

    assert merged.meta.site_name == "Acme (already reviewed)"


def test_merge_full_blueprint_does_not_mutate_its_inputs():
    home = _doc("Acme", ["https://example.com/"])
    remaining = _doc("ignored", ["https://example.com/about"])

    _merge_full_blueprint(home, remaining)

    assert len(home.pages) == 1
    assert len(remaining.pages) == 1
