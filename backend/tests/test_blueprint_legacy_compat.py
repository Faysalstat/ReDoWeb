from app.ai.blueprint_legacy_compat import render_design_md_compat
from app.ai.blueprint_schema import (
    AdditionalSection,
    BlueprintDocument,
    ColorPalette,
    Fonts,
    FooterSection,
    GalleryItem,
    HeroSection,
    MetaBlock,
    NavLink,
    PageBlueprint,
    PageSections,
    SocialLink,
)


def _make_blueprint(sections: PageSections) -> BlueprintDocument:
    return BlueprintDocument(
        meta=MetaBlock(
            site_name="Acme Co",
            colors=ColorPalette(primary="#111111", secondary="#222222", accent="#333333"),
            fonts=Fonts(heading="Inter", body="Inter"),
        ),
        pages=[PageBlueprint(page_url="https://acme.example.com/", sections=sections)],
    )


def test_render_includes_additional_sections_body_and_items():
    sections = PageSections(
        hero=HeroSection(headline="Welcome"),
        additional_sections=[
            AdditionalSection(
                key="lifetime-warranty",
                title="Lifetime Warranty!",
                body="We guarantee our products for life.",
                items=["Rust proof", "Commercial grade"],
            )
        ],
    )

    design_md = render_design_md_compat(_make_blueprint(sections))

    assert "### Lifetime Warranty!" in design_md
    assert "We guarantee our products for life." in design_md
    assert "- Rust proof" in design_md
    assert "- Commercial grade" in design_md


def test_render_includes_multiple_additional_sections_in_order():
    sections = PageSections(
        hero=HeroSection(headline="Welcome"),
        additional_sections=[
            AdditionalSection(key="a", title="First Extra", body="First body"),
            AdditionalSection(key="b", title="Second Extra", body="Second body"),
        ],
    )

    design_md = render_design_md_compat(_make_blueprint(sections))

    first_index = design_md.index("### First Extra")
    second_index = design_md.index("### Second Extra")
    assert first_index < second_index
    assert "First body" in design_md
    assert "Second body" in design_md


def test_render_omits_additional_sections_heading_when_empty():
    sections = PageSections(hero=HeroSection(headline="Welcome"), additional_sections=[])

    design_md = render_design_md_compat(_make_blueprint(sections))

    assert "additional_sections" not in design_md.lower()


def test_render_includes_gallery_portfolio_captions():
    sections = PageSections(
        hero=HeroSection(headline="Welcome"),
        gallery_portfolio=[GalleryItem(image="snapshot/image/a.jpg", caption="Finished patio")],
    )

    design_md = render_design_md_compat(_make_blueprint(sections))

    assert "### Gallery" in design_md
    assert "Finished patio" in design_md


def test_render_includes_footer_links_and_copyright():
    sections = PageSections(
        hero=HeroSection(headline="Welcome"),
        footer=FooterSection(
            links=[NavLink(label="Privacy", href="/privacy")],
            social_links=[SocialLink(platform="Instagram", url="https://instagram.com/acme")],
            copyright_text="(c) 2026 Acme Co",
        ),
    )

    design_md = render_design_md_compat(_make_blueprint(sections))

    assert "### Footer" in design_md
    assert "Privacy (/privacy)" in design_md
    assert "Instagram: https://instagram.com/acme" in design_md
    assert "(c) 2026 Acme Co" in design_md


def test_render_omits_footer_heading_when_footer_is_empty():
    sections = PageSections(hero=HeroSection(headline="Welcome"), footer=FooterSection())

    design_md = render_design_md_compat(_make_blueprint(sections))

    assert "### Footer" not in design_md
