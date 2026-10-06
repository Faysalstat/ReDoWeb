"""Deterministic half of the SEO pass (app/ai/seo_postprocess.py): the
mechanical checklist items and the code-enforced safety nets around what
the agent wrote. Tests the code's behavior on fixed HTML, not AI output."""

import json

from PIL import Image

from app.ai.blueprint_schema import BlueprintDocument
from app.ai.postprocess import page_url, postprocess_output, site_origin_from_url
from app.ai.seo_postprocess import (
    IMG_HEIGHT_GUARD_MARKER,
    audit_seo,
    blueprint_facts,
    finalize_seo,
    heading_retag_safe,
    optimize_images,
    sanitize_jsonld,
)
from bs4 import BeautifulSoup

ORIGIN = "https://example.com"


def _blueprint(**contact):
    sections = {"contact": contact} if contact else {}
    return BlueprintDocument.model_validate(
        {
            "meta": {
                "site_name": "Acme",
                "tagline": "Builders you can trust",
                "logo": "snapshot/image/logo.png",
                "colors": {"primary": "#111111", "secondary": "#ffffff", "accent": "#333333"},
                "fonts": {"heading": "Inter", "body": "Inter"},
            },
            "pages": [{"page_url": "https://example.com/", "sections": sections}],
        }
    )


def _site(tmp_path, html, css=".hero{color:red}"):
    (tmp_path / "images").mkdir()
    Image.new("RGB", (800, 400), "white").save(tmp_path / "images" / "logo.png")
    Image.new("RGB", (1200, 600), "blue").save(tmp_path / "images" / "hero.jpg")
    (tmp_path / "style.css").write_text(css, encoding="utf-8")
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    return tmp_path


PAGE = """<!DOCTYPE html><html><head><title>Acme</title>
<meta name="robots" content="noindex, nofollow">
<link rel="stylesheet" href="style.css">
<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
<script src="script.js"></script>
</head><body>
<header><img src="images/logo.png" alt="Acme logo"></header>
<main><h1>Hi</h1><img src="images/hero.jpg" alt="Kitchen"><img src="images/hero.jpg" alt="x">
<a href="http://example.com/contact">Contact</a><a href="about.html">About</a></main>
</body></html>"""


# --- site_origin_from_url / postprocess sitemap (every tier) --------------


def test_site_origin_from_url_is_https_host_only():
    assert site_origin_from_url("http://www.example.com/about?x=1") == "https://www.example.com"
    assert site_origin_from_url("https://user:pw@Shop.Example.co.uk:8443/x") == "https://shop.example.co.uk:8443"
    assert site_origin_from_url("") is None
    assert site_origin_from_url("not a url") is None
    assert site_origin_from_url(None) is None


def test_page_url_maps_index_to_site_root():
    assert page_url(ORIGIN, "index.html") == "https://example.com/"
    assert page_url(ORIGIN, "about-us.html") == "https://example.com/about-us.html"


def test_postprocess_sitemap_uses_real_domain_when_known(tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>A</title></head><body></body></html>", encoding="utf-8")

    postprocess_output(tmp_path, {}, site_origin=ORIGIN)

    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.com/</loc>" in sitemap
    assert "REPLACE-WITH-YOUR-DOMAIN" not in sitemap
    assert 'content="https://example.com/"' in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_postprocess_sitemap_falls_back_to_placeholder_without_origin(tmp_path):
    (tmp_path / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")

    postprocess_output(tmp_path, {})

    assert "REPLACE-WITH-YOUR-DOMAIN" in (tmp_path / "sitemap.xml").read_text(encoding="utf-8")


# --- finalize_seo: mechanical items ---------------------------------------


def test_finalize_seo_applies_head_files_and_performance_fixes(tmp_path):
    site = _site(tmp_path, PAGE)
    (site / "script.js").write_text("", encoding="utf-8")

    report = finalize_seo(site, _blueprint(), ORIGIN)

    soup = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert soup.html["lang"] == "en"
    assert soup.find("meta", charset=True)
    assert soup.find("meta", attrs={"name": "viewport"})
    assert soup.find("meta", attrs={"name": "robots"}) is None  # noindex/nofollow stripped
    assert soup.find("link", rel="canonical")["href"] == "https://example.com/"
    assert soup.find("meta", property="og:url")["content"] == "https://example.com/"
    assert soup.find("meta", property="og:image")["content"] == "https://example.com/images/logo.png"
    assert soup.find("meta", property="og:site_name")["content"] == "Acme"
    assert soup.find("meta", attrs={"name": "twitter:card"})
    assert soup.find("a", string="Contact")["href"] == "https://example.com/contact"  # same-origin http -> https
    assert {link["href"] for link in soup.find_all("link", rel="preconnect")} == {
        "https://fonts.googleapis.com",
        "https://fonts.gstatic.com",
    }
    assert soup.find("script", src="script.js").has_attr("defer")

    logo, hero, second = soup.find_all("img")
    assert (hero["width"], hero["height"]) == ("1200", "600")
    assert hero["fetchpriority"] == "high" and not hero.get("loading")  # first CONTENT image = LCP
    assert not logo.get("loading")  # header logo is never lazy-loaded
    assert second["loading"] == "lazy" and second["decoding"] == "async"
    assert IMG_HEIGHT_GUARD_MARKER in (site / "style.css").read_text(encoding="utf-8")

    assert "https://example.com/sitemap.xml" in (site / "robots.txt").read_text(encoding="utf-8")
    assert "<loc>https://example.com/</loc>" in (site / "sitemap.xml").read_text(encoding="utf-8")
    llms = (site / "llms.txt").read_text(encoding="utf-8")
    assert llms.startswith("# Acme") and "(https://example.com/)" in llms
    assert (site / "SEO-NEXT-STEPS.md").exists()
    assert "index.html" in report["noindex_removed"]
    # The broken about.html link is still reported for the agent/final report.
    assert any("about.html" in issue for issue in report["remaining_issues"]["index.html"])


def test_finalize_seo_is_idempotent(tmp_path):
    site = _site(tmp_path, PAGE)
    finalize_seo(site, _blueprint(), ORIGIN)
    html_once = (site / "index.html").read_text(encoding="utf-8")
    css_once = (site / "style.css").read_text(encoding="utf-8")

    finalize_seo(site, _blueprint(), ORIGIN)

    assert (site / "index.html").read_text(encoding="utf-8") == html_once
    assert (site / "style.css").read_text(encoding="utf-8") == css_once
    soup = BeautifulSoup(html_once, "lxml")
    assert len(soup.find_all("link", rel="canonical")) == 1
    assert len(soup.find_all("meta", property="og:url")) == 1


def test_defer_skipped_when_an_inline_script_could_depend_on_local_script(tmp_path):
    html = PAGE.replace("</body>", "<script>initSlider();</script></body>")
    site = _site(tmp_path, html)

    finalize_seo(site, _blueprint(), ORIGIN)

    soup = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert not soup.find("script", src="script.js").has_attr("defer")


def test_img_height_guard_injected_inline_when_no_local_stylesheet(tmp_path):
    html = '<html><head><script src="https://cdn.tailwindcss.com"></script></head><body><main><img src="images/hero.jpg" alt="Kitchen"></main></body></html>'
    site = _site(tmp_path, html)

    finalize_seo(site, _blueprint(), ORIGIN)
    finalize_seo(site, _blueprint(), ORIGIN)

    soup = BeautifulSoup((site / "index.html").read_text(encoding="utf-8"), "lxml")
    assert len(soup.find_all("style", attrs={"data-seo-guard": True})) == 1


# --- JSON-LD validation + anti-fabrication ---------------------------------


def test_invalid_jsonld_is_dropped(tmp_path):
    html = PAGE.replace("</head>", '<script type="application/ld+json">{not json</script></head>')
    site = _site(tmp_path, html)

    report = finalize_seo(site, _blueprint(), ORIGIN)

    assert "index.html" in report["jsonld_dropped_invalid"]
    assert "{not json" not in (site / "index.html").read_text(encoding="utf-8")


def test_jsonld_fabricated_contact_and_ratings_are_stripped_real_ones_kept():
    facts = blueprint_facts(_blueprint(phone="(512) 555-0100", email="hi@acme.com", address="12 Main St, Austin TX"))
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": "Acme",
        "telephone": "+1 512-555-0100",
        "email": "sales@acme.com",
        "address": {"@type": "PostalAddress", "streetAddress": "12 Main St", "addressLocality": "Austin"},
        "aggregateRating": {"ratingValue": "4.9", "reviewCount": "120"},
        "offers": {"price": "99"},
    }
    removed: list[str] = []

    cleaned = sanitize_jsonld(data, facts, removed)

    assert cleaned["telephone"] == "+1 512-555-0100"  # matches the real number
    assert "address" in cleaned  # every part appears in the real address
    assert "email" not in cleaned  # not the site's real email
    assert "aggregateRating" not in cleaned and "offers" not in cleaned  # no testimonials/pricing on the site
    assert len(removed) == 3


def test_jsonld_contact_stripped_when_site_has_no_contact_details_including_graph():
    facts = blueprint_facts(_blueprint())
    data = {"@graph": [{"@type": "Organization", "name": "Acme", "telephone": "555-1234", "address": "1 Fake Rd"}]}
    removed: list[str] = []

    cleaned = sanitize_jsonld(data, facts, removed)

    assert cleaned == {"@graph": [{"@type": "Organization", "name": "Acme"}]}


# --- audit / heading safety -------------------------------------------------


def test_heading_retag_safe_false_for_bare_heading_css_and_bootstrap(tmp_path):
    site = _site(tmp_path, PAGE, css="h1{font-size:4rem}")
    assert not heading_retag_safe(site, BeautifulSoup(PAGE, "lxml"))

    (site / "style.css").write_text("section > h2:hover{color:red}", encoding="utf-8")
    assert not heading_retag_safe(site, BeautifulSoup(PAGE, "lxml"))

    # Still styles headings BY TAG (inside .hero), so retagging would change the look.
    (site / "style.css").write_text(".hero h1{color:red}", encoding="utf-8")
    assert not heading_retag_safe(site, BeautifulSoup(PAGE, "lxml"))

    # Class-only rules (Tailwind-style): retagging changes nothing visually.
    (site / "style.css").write_text(".hero{color:red} .title-xl{font-size:3rem}", encoding="utf-8")
    assert heading_retag_safe(site, BeautifulSoup(PAGE, "lxml"))

    bootstrap = PAGE.replace(
        "</head>", '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"></head>'
    )
    (site / "style.css").write_text(".x{}", encoding="utf-8")
    assert not heading_retag_safe(site, BeautifulSoup(bootstrap, "lxml"))


def test_audit_reports_h1_count_skips_alt_and_broken_links(tmp_path):
    html = (
        "<html><head><title>A</title></head><body><main><h1>a</h1><h1>b</h1><h4>c</h4>"
        '<img src="images/hero.jpg"><img src="images/hero.jpg" alt="Image">'
        '<a href="#missing">x</a><a href="nope.html">y</a></main></body></html>'
    )
    site = _site(tmp_path, html)

    page = audit_seo(site)["pages"]["index.html"]

    assert page["h1_count"] == 2
    assert page["heading_skips"] == ["h1 -> h4"]
    assert len(page["images_missing_or_weak_alt"]) == 2
    assert set(page["broken_links"]) == {"#missing", "nope.html"}


# --- image compression ------------------------------------------------------


def test_optimize_images_downscales_wide_images_same_name_and_skips_svg_and_corrupt(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    Image.new("RGB", (3000, 1500), "red").save(images / "big.jpg", quality=100)
    (images / "icon.svg").write_text("<svg/>", encoding="utf-8")
    (images / "broken.png").write_bytes(b"not an image")

    results = optimize_images(images)

    with Image.open(images / "big.jpg") as img:
        assert img.size == (1920, 960)
        assert img.format == "JPEG"
    assert (images / "icon.svg").read_text(encoding="utf-8") == "<svg/>"
    assert (images / "broken.png").read_bytes() == b"not an image"
    assert not list(images.glob("*.seo-tmp"))
    assert any("big.jpg" in r for r in results)
