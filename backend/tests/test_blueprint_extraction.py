from bs4 import BeautifulSoup

from app.ai.blueprint_extraction import _extract_page, _resolve_image

SAMPLE_HTML = """
<html><head><title>Acme Co - Home</title></head>
<body>
<header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
<main>
<h1>Welcome to Acme Co</h1>
<p>We build great things.</p>
<a class="btn" href="/contact">Get Started</a>
<h2>About Us</h2>
<p>Acme Co was founded in 2010.</p>
<h2>Our Services</h2>
<h3>Web Design</h3>
<p>We design websites.</p>
<h3>SEO</h3>
<p>We do SEO.</p>
</main>
<footer><p>&copy; 2026 Acme Co</p></footer>
</body></html>
"""


def test_resolve_image_never_fabricates_undownloaded_asset():
    soup = BeautifulSoup('<img src="/img/logo.png">', "lxml")
    img = soup.find("img")

    assert _resolve_image(img, "https://example.com/", {}) is None


def test_resolve_image_returns_storage_path_for_known_asset():
    soup = BeautifulSoup('<img src="/img/logo.png">', "lxml")
    img = soup.find("img")
    assets_by_url = {
        "https://example.com/img/logo.png": {
            "original_url": "https://example.com/img/logo.png",
            "asset_type": "image",
            "storage_path": "snapshot/image/abc123-logo.png",
        }
    }

    assert _resolve_image(img, "https://example.com/", assets_by_url) == "snapshot/image/abc123-logo.png"


def test_extract_page_buckets_hero_about_and_services():
    page = _extract_page("https://example.com/", SAMPLE_HTML, assets_by_url={})
    sections = page.sections

    assert sections.hero.headline == "Welcome to Acme Co"
    assert sections.hero.subheadline == "We build great things."
    assert sections.hero.cta_text == "Get Started"
    assert sections.hero.cta_href == "/contact"

    assert sections.about.heading == "About Us"
    assert "founded in 2010" in sections.about.body

    titles = {item.title for item in sections.services_features}
    assert titles == {"Web Design", "SEO"}


def test_extract_page_derives_footer_structurally():
    page = _extract_page("https://example.com/", SAMPLE_HTML, assets_by_url={})

    assert "2026 Acme Co" in page.sections.footer.copyright_text


def test_extract_page_leaves_optional_sections_empty_when_not_present():
    page = _extract_page("https://example.com/", SAMPLE_HTML, assets_by_url={})
    sections = page.sections

    assert sections.testimonials == []
    assert sections.team == []
    assert sections.pricing == []
    assert sections.contact.email == ""
    assert sections.contact.phone == ""


# --- Page-builder markup fallbacks (no semantic <nav>/<footer> tags) -------

PAGE_BUILDER_HTML = """
<html><head><title>Widget Co</title></head>
<body>
<header class="entry-header">Widget Co</header>
<div class="elementor elementor-location-header">
<a href="/">Home</a>
<a href="/services">Services</a>
<a href="tel:1234567890">Call Us</a>
<a href="https://facebook.com/widgetco">Facebook</a>
</div>
<main>
<h1>Welcome to Widget Co</h1>
<span class="elementor-testimonial__footer">not a real footer, just a widget's internal class</span>
</main>
<div class="elementor elementor-location-footer">
<p>&copy; 2026 Widget Co</p>
<a href="/privacy">Privacy Policy</a>
<a href="https://facebook.com/widgetco">Facebook</a>
</div>
</body></html>
"""


def test_navigation_falls_back_to_header_location_class_over_wrong_header_tag():
    soup = BeautifulSoup(PAGE_BUILDER_HTML, "lxml")
    from app.ai.blueprint_extraction import _extract_navigation

    links = _extract_navigation(soup)

    labels = {link.label for link in links}
    assert labels == {"Home", "Services"}  # tel: and social links excluded


def test_footer_falls_back_to_location_footer_class_ignoring_widget_internal_class():
    soup = BeautifulSoup(PAGE_BUILDER_HTML, "lxml")
    from app.ai.blueprint_extraction import _extract_footer

    footer = _extract_footer(soup)

    assert "2026 Widget Co" in footer.copyright_text
    assert {link.label for link in footer.links} == {"Privacy Policy"}
    assert len(footer.social_links) == 1
    assert footer.social_links[0].url == "https://facebook.com/widgetco"


# --- Duplicate-block dedup (Elementor-style responsive DOM duplication) ----

DUPLICATED_SERVICES_HTML = """
<html><head><title>Widget Co</title></head>
<body>
<main>
<h1>Welcome</h1>
<h2>Our Services</h2>
<h3>Web Design</h3>
<p>We design great websites.</p>
<h3>Web Design</h3>
<p>We design great websites.</p>
<h3>SEO</h3>
<p>We do SEO.</p>
</main>
</body></html>
"""


def test_duplicate_service_items_are_deduped():
    page = _extract_page("https://example.com/", DUPLICATED_SERVICES_HTML, assets_by_url={})

    titles = [item.title for item in page.sections.services_features]
    assert titles == ["Web Design", "SEO"]


# --- all_images completeness net -------------------------------------------

IMAGES_HTML = """
<html><head></head>
<body>
<main>
<img src="/img/a.png" alt="A">
<img src="/img/a.png" alt="A duplicate">
<img src="/img/b.png" alt="B">
<img src="/img/not-downloaded.png" alt="Missing">
</main>
</body></html>
"""


def test_all_images_includes_every_downloaded_image_deduped_by_path():
    assets_by_url = {
        "https://example.com/img/a.png": {"original_url": "https://example.com/img/a.png", "asset_type": "image", "storage_path": "snapshot/image/a.png"},
        "https://example.com/img/b.png": {"original_url": "https://example.com/img/b.png", "asset_type": "image", "storage_path": "snapshot/image/b.png"},
    }

    page = _extract_page("https://example.com/", IMAGES_HTML, assets_by_url=assets_by_url)

    paths = [img.path for img in page.all_images]
    assert paths == ["snapshot/image/a.png", "snapshot/image/b.png"]
    assert page.all_images[0].alt == "A"  # first occurrence's alt kept on dedup


# --- Leaf-div/span text capture (page-builders wrap prose in divs, not <p>) -

DIV_PROSE_HTML = """
<html><head><title>Acme Co</title></head>
<body>
<main>
<h1>Welcome</h1>
<h2>About Us</h2>
<div>Acme Co has been serving the community for over twenty five years with pride.</div>
<div>Icon</div>
</main>
</body></html>
"""


def test_leaf_div_text_is_captured_but_short_incidental_div_is_not():
    page = _extract_page("https://example.com/", DIV_PROSE_HTML, assets_by_url={})

    assert "twenty five years" in page.sections.about.body
    assert "Icon" not in page.sections.about.body


# --- Elementor testimonial-carousel widget detection ------------------------
# Real markup shape confirmed from an actual crawled site (fix2live.com) --
# no governing heading, quote/author wrapped in <div>/<span>, not <p>.

TESTIMONIAL_WIDGET_HTML = """
<html><head><title>Fix2Live</title></head>
<body>
<main>
<h1>Welcome</h1>
<div class="elementor-widget-testimonial-carousel">
<div class="elementor-testimonial">
  <div class="elementor-testimonial__content">
    <div class="elementor-testimonial__text">I had use another company to help me with my credit. After 10 months there was no improvement on my report.</div>
  </div>
  <div class="elementor-testimonial__footer">
    <cite class="elementor-testimonial__cite"><span class="elementor-testimonial__name">Tommy R.</span></cite>
  </div>
</div>
<div class="elementor-testimonial">
  <div class="elementor-testimonial__content">
    <div class="elementor-testimonial__text">Great service, highly recommend them to anyone looking for credit repair help.</div>
  </div>
  <div class="elementor-testimonial__footer">
    <cite class="elementor-testimonial__cite"><span class="elementor-testimonial__name">Jane D.</span></cite>
  </div>
</div>
</div>
</main>
</body></html>
"""


def test_elementor_testimonial_widget_is_extracted_with_no_governing_heading():
    page = _extract_page("https://example.com/", TESTIMONIAL_WIDGET_HTML, assets_by_url={})

    quotes = {item.quote: item.author for item in page.sections.testimonials}
    assert quotes == {
        "I had use another company to help me with my credit. After 10 months there was no improvement on my report.": "Tommy R.",
        "Great service, highly recommend them to anyone looking for credit repair help.": "Jane D.",
    }


def test_elementor_testimonial_widget_deduped_on_responsive_duplicate_markup():
    from app.ai.blueprint_extraction import _extract_elementor_testimonials

    soup = BeautifulSoup(TESTIMONIAL_WIDGET_HTML + TESTIMONIAL_WIDGET_HTML, "lxml")  # simulate duplicated DOM

    items = _extract_elementor_testimonials(soup, "https://example.com/", {})

    assert len(items) == 2  # not 4


def test_widget_detection_does_not_override_already_classified_testimonials():
    from app.ai.blueprint_extraction import _extract_widget_sections
    from app.ai.blueprint_schema import PageSections, TestimonialItem

    soup = BeautifulSoup(TESTIMONIAL_WIDGET_HTML, "lxml")
    sections = PageSections(testimonials=[TestimonialItem(quote="Already classified", author="Existing")])

    _extract_widget_sections(soup, "https://example.com/", {}, sections)

    assert len(sections.testimonials) == 1
    assert sections.testimonials[0].quote == "Already classified"


# --- additional_sections: real content that matches no known section key ---

UNCLASSIFIED_SECTION_HTML = """
<html><head><title>Acme Co</title></head>
<body>
<main>
<h1>Welcome</h1>
<h2>Our Coverage Map</h2>
<p>We proudly cover Orlando, Kissimmee, and the surrounding Central Florida region.</p>
</main>
</body></html>
"""


# --- CTA href filtering (javascript:/bare "#" are dead links on a static site)

JS_CTA_HTML = """
<html><head><title>Acme Co</title></head>
<body>
<main>
<h1>Welcome</h1>
<a class="btn" href="javascript:void(0)" onclick="openModal()">Get Started</a>
<p>We build great things.</p>
</main>
</body></html>
"""

TEL_CTA_HTML = """
<html><head><title>Acme Co</title></head>
<body>
<main>
<h1>Welcome</h1>
<a class="btn" href="tel:+13213374975">Call Now</a>
<p>We build great things.</p>
</main>
</body></html>
"""


def test_javascript_cta_href_is_dropped_not_copied_verbatim():
    page = _extract_page("https://example.com/", JS_CTA_HTML, assets_by_url={})

    assert page.sections.hero.cta_text == ""
    assert page.sections.hero.cta_href == ""


def test_tel_cta_href_is_kept_as_a_legitimate_cta():
    page = _extract_page("https://example.com/", TEL_CTA_HTML, assets_by_url={})

    assert page.sections.hero.cta_text == "Call Now"
    assert page.sections.hero.cta_href == "tel:+13213374975"


# --- Fix A: hero detection when the page has no <h1> at all ----------------

NO_H1_HTML = """
<html><head><title>Widget Co</title></head>
<body>
<main>
<h2>Leaders in Widget Solutions</h2>
<p>We build the best widgets around.</p>
<h2>About Us</h2>
<p>Founded in 2010.</p>
</main>
</body></html>
"""


def test_hero_uses_first_heading_when_no_h1_exists_on_page():
    page = _extract_page("https://example.com/", NO_H1_HTML, assets_by_url={})

    assert page.sections.hero.headline == "Leaders in Widget Solutions"
    assert page.sections.hero.subheadline == "We build the best widgets around."
    assert page.sections.about.heading == "About Us"  # still correctly classified after the hero


# --- Fix B: contact info in header/footer text, outside any body block -----

HEADER_FOOTER_CONTACT_HTML = """
<html><head><title>Widget Co</title></head>
<body>
<div class="elementor elementor-location-header">
<a href="tel:+13215551234"><span>(321) 555-1234</span></a>
</div>
<main>
<h1>Welcome</h1>
<p>We build great things.</p>
</main>
<div class="elementor elementor-location-footer">
<p>Reach us at hello@widgetco.com</p>
</div>
</body></html>
"""


def test_contact_fallback_finds_phone_in_header_and_email_in_footer():
    page = _extract_page("https://example.com/", HEADER_FOOTER_CONTACT_HTML, assets_by_url={})

    assert page.sections.contact.phone == "(321) 555-1234"
    assert page.sections.contact.email == "hello@widgetco.com"


# --- Fix C: mega-footer content (its own real headings) ---------------------

MEGA_FOOTER_HTML = """
<html><head><title>Widget Co</title></head>
<body>
<main>
<h1>Welcome to Widget Co</h1>
<p>We build great things.</p>
</main>
<footer>
<h2>ABOUT</h2>
<p>Widget Co has served the community since 2005 with pride and dedication.</p>
<h2>GET IN TOUCH</h2>
<p>Call us at (321) 555-9999 or email hello@widgetco.com anytime.</p>
</footer>
</body></html>
"""


def test_footer_mega_section_fills_about_and_contact_when_main_is_empty():
    page = _extract_page("https://example.com/", MEGA_FOOTER_HTML, assets_by_url={})

    assert "served the community since 2005" in page.sections.about.body
    assert page.sections.contact.email == "hello@widgetco.com"
    assert page.sections.contact.phone == "(321) 555-9999"


MEGA_FOOTER_WITH_MAIN_ABOUT_HTML = """
<html><head><title>Widget Co</title></head>
<body>
<main>
<h1>Welcome to Widget Co</h1>
<h2>About Us</h2>
<p>Real main about content here spanning enough words to count.</p>
</main>
<footer>
<h2>ABOUT</h2>
<p>Footer about blurb that should NOT override the main one.</p>
</footer>
</body></html>
"""


def test_footer_mega_section_does_not_override_existing_main_about():
    page = _extract_page("https://example.com/", MEGA_FOOTER_WITH_MAIN_ABOUT_HTML, assets_by_url={})

    assert "Real main about content" in page.sections.about.body
    assert "Footer about blurb" not in page.sections.about.body


def test_unclassified_heading_becomes_additional_section_not_merged_into_about():
    page = _extract_page("https://example.com/", UNCLASSIFIED_SECTION_HTML, assets_by_url={})

    assert len(page.sections.additional_sections) == 1
    section = page.sections.additional_sections[0]
    assert section.title == "Our Coverage Map"
    assert section.key == "our-coverage-map"
    assert "Orlando" in section.body
    assert page.sections.about.body == ""  # not force-merged into about
