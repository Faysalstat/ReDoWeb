"""Deterministic design-consistency guards for the all-pages build -- see
app/ai/site_consistency.py and docs/seo-agent-and-buy-flow-plan.md (D1-D6,
breakage item 5a). These test the code's behavior against fixed HTML/CSS,
not any AI output."""

import json

from app.ai import site_generator
from app.ai.site_consistency import (
    enforce_shared_head,
    guard_appended_css,
    rewrite_internal_links,
    shared_shell_excerpt,
    sync_site_chrome,
)

HOME = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Acme</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config = {theme: {extend: {colors: {brand: '#111'}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet"/>
<link href="style.css" rel="stylesheet"/>
</head><body>
<header class="site-header"><nav><a href="https://www.example.com/about-us/">About</a><a href="/contact">Contact</a><a href="#top">Top</a></nav></header>
<main><h1>Welcome</h1><a href="https://other.org/x">External</a></main>
<footer class="site-footer"><a href="http://example.com/contact#form">Write to us</a></footer>
</body></html>"""

PAGE_URLS = ["https://example.com/", "https://example.com/about-us", "https://example.com/contact"]
FILENAMES = ["index.html", "about-us.html", "contact.html"]


def _write(dir_, name, text):
    (dir_ / name).write_text(text, encoding="utf-8")
    return dir_ / name


# --- rewrite_internal_links (breakage 5a) ---------------------------------


def test_rewrite_internal_links_maps_crawled_url_variants_to_local_files(tmp_path):
    _write(tmp_path, "index.html", HOME)

    changes = rewrite_internal_links(tmp_path, PAGE_URLS, FILENAMES)

    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'href="about-us.html"' in html  # www. + trailing slash + https
    assert 'href="contact.html"' in html  # root-relative
    assert 'href="contact.html#form"' in html  # http + fragment kept
    assert 'href="#top"' in html  # in-page anchor untouched
    assert 'href="https://other.org/x"' in html  # external untouched
    assert len(changes) == 3


def test_rewrite_internal_links_leaves_unmatched_file_byte_identical(tmp_path):
    original = "<html><body><a href='https://other.org/'>x</a></body></html>"
    _write(tmp_path, "index.html", original)

    assert rewrite_internal_links(tmp_path, PAGE_URLS, FILENAMES) == []
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == original


def test_rewrite_internal_links_keeps_query_string_links_alone(tmp_path):
    _write(tmp_path, "index.html", '<html><body><a href="/contact?ref=nav">c</a></body></html>')

    assert rewrite_internal_links(tmp_path, PAGE_URLS, FILENAMES) == []


# --- enforce_shared_head (D4) ---------------------------------------------


def test_enforce_shared_head_adds_missing_assets_in_order_and_never_removes(tmp_path):
    _write(tmp_path, "index.html", HOME)
    _write(
        tmp_path,
        "about-us.html",
        '<html><head><title>About</title><link href="extra.css" rel="stylesheet"/></head><body></body></html>',
    )

    changes = enforce_shared_head(tmp_path)

    html = (tmp_path / "about-us.html").read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" in html
    assert "tailwind.config" in html
    assert "fonts.googleapis.com" in html
    assert 'href="style.css"' in html
    assert 'href="extra.css"' in html  # the page's own asset is kept
    assert "<title>About</title>" in html  # page-specific head untouched
    # Tailwind CDN must load before its inline config.
    assert html.index("cdn.tailwindcss.com") < html.index("tailwind.config")
    assert len(changes) == 4


def test_enforce_shared_head_is_idempotent(tmp_path):
    _write(tmp_path, "index.html", HOME)
    _write(tmp_path, "about-us.html", "<html><head><title>About</title></head><body></body></html>")

    enforce_shared_head(tmp_path)
    once = (tmp_path / "about-us.html").read_text(encoding="utf-8")
    assert enforce_shared_head(tmp_path) == []
    assert (tmp_path / "about-us.html").read_text(encoding="utf-8") == once


def test_enforce_shared_head_inserts_cdn_before_existing_config(tmp_path):
    _write(tmp_path, "index.html", HOME)
    _write(
        tmp_path,
        "about-us.html",
        "<html><head><script>tailwind.config = {theme: {extend: {colors: {brand: '#111'}}}}</script>"
        "</head><body></body></html>",
    )

    enforce_shared_head(tmp_path)

    html = (tmp_path / "about-us.html").read_text(encoding="utf-8")
    assert html.index("cdn.tailwindcss.com") < html.index("tailwind.config")


# --- sync_site_chrome (D5) ------------------------------------------------


def test_sync_site_chrome_replaces_nav_header_and_footer_with_home_copy(tmp_path):
    _write(tmp_path, "index.html", HOME)
    _write(
        tmp_path,
        "about-us.html",
        "<html><body><header><nav><a href='x.html'>Different</a></nav></header>"
        "<main><h1>About</h1></main><footer>Old footer</footer></body></html>",
    )

    changes = sync_site_chrome(tmp_path)

    html = (tmp_path / "about-us.html").read_text(encoding="utf-8")
    assert 'class="site-header"' in html
    assert 'class="site-footer"' in html
    assert "Different" not in html and "Old footer" not in html
    assert "<h1>About</h1>" in html  # page body untouched
    assert len(changes) == 2


def test_sync_site_chrome_never_replaces_a_page_header_holding_its_own_h1(tmp_path):
    _write(tmp_path, "index.html", HOME)
    _write(
        tmp_path,
        "about-us.html",
        "<html><body><header><nav>n</nav><h1>About hero</h1></header><footer>f</footer></body></html>",
    )

    sync_site_chrome(tmp_path)

    html = (tmp_path / "about-us.html").read_text(encoding="utf-8")
    assert "About hero" in html
    assert 'class="site-footer"' in html


def test_sync_site_chrome_skips_home_header_with_hero_and_uses_nav_instead(tmp_path):
    home = (
        "<html><body><header><nav class='main-nav'><a href='about-us.html'>About</a></nav>"
        "<h1>Big hero</h1></header><footer>f</footer></body></html>"
    )
    _write(tmp_path, "index.html", home)
    _write(tmp_path, "about-us.html", "<html><body><nav>old</nav><main><h1>About</h1></main></body></html>")

    sync_site_chrome(tmp_path)

    html = (tmp_path / "about-us.html").read_text(encoding="utf-8")
    assert "Big hero" not in html
    assert "main-nav" not in html  # nav sits inside the hero header -> not treated as shared chrome


def test_sync_site_chrome_does_not_add_missing_elements(tmp_path):
    _write(tmp_path, "index.html", HOME)
    original = "<html><body><main><h1>About</h1></main></body></html>"
    _write(tmp_path, "about-us.html", original)

    assert sync_site_chrome(tmp_path) == []
    assert (tmp_path / "about-us.html").read_text(encoding="utf-8") == original


# --- guard_appended_css (D2) ----------------------------------------------

ORIGINAL_CSS = ".btn{color:red}\n.card{padding:1rem}\n"


def test_guard_appended_css_strips_global_and_redefined_rules_keeps_new_classes(tmp_path):
    appended = (
        ORIGINAL_CSS.rstrip("\n")
        + "\n\n/* new page */\nbody{background:black}\nh1, .team-grid h3{font-size:9rem}\n"
        ".btn{color:blue}\n.team-grid{display:grid}\n:root{--brand:#000}\n"
        "@media (min-width: 640px){ .team-grid{gap:2rem} section{margin:0} }\n"
        "@keyframes pop{from{opacity:0}to{opacity:1}}\n"
    )
    css_path = _write(tmp_path, "style.css", appended)

    stripped = guard_appended_css(css_path, ORIGINAL_CSS)

    final = css_path.read_text(encoding="utf-8")
    assert final.startswith(ORIGINAL_CSS.rstrip("\n"))  # original untouched
    assert "background:black" not in final
    assert "color:blue" not in final
    assert "--brand" not in final
    assert "margin:0" not in final
    assert ".team-grid{display:grid}" in final.replace(" {", "{")
    assert ".team-grid h3" in final  # the class-qualified half of a mixed selector list survives
    assert "gap:2rem" in final
    assert "@keyframes pop" in final
    assert any("body" in s for s in stripped)
    assert any(".btn" in s and "already defined" in s for s in stripped)


def test_guard_appended_css_leaves_clean_append_byte_identical(tmp_path):
    text = ORIGINAL_CSS.rstrip("\n") + "\n\n.team-grid{display:grid}\n"
    css_path = _write(tmp_path, "style.css", text)

    assert guard_appended_css(css_path, ORIGINAL_CSS) == []
    assert css_path.read_text(encoding="utf-8") == text


def test_guard_appended_css_leaves_unparseable_css_alone(tmp_path):
    text = ORIGINAL_CSS.rstrip("\n") + "\n\nbody{color:red\n"
    css_path = _write(tmp_path, "style.css", text)

    assert guard_appended_css(css_path, ORIGINAL_CSS) == []
    assert css_path.read_text(encoding="utf-8") == text


def test_guard_appended_css_ignores_untouched_stylesheet(tmp_path):
    css_path = _write(tmp_path, "style.css", ORIGINAL_CSS)

    assert guard_appended_css(css_path, ORIGINAL_CSS) == []


# --- shared_shell_excerpt (D3) --------------------------------------------


def test_shared_shell_excerpt_includes_head_assets_and_chrome_not_page_body():
    excerpt = shared_shell_excerpt(HOME)

    assert "cdn.tailwindcss.com" in excerpt
    assert "tailwind.config" in excerpt
    assert 'class="site-header"' in excerpt
    assert 'class="site-footer"' in excerpt
    assert "Welcome" not in excerpt  # the home page's own <h1> body content
    assert "<title>" not in excerpt


# --- generate_full_site wiring (D1) ---------------------------------------


def _make_project(tmp_path):
    project_root = tmp_path / "project"
    blueprint_dir = project_root / "blueprint"
    blueprint_dir.mkdir(parents=True)
    preview_dir = project_root / "generated" / "pro"
    preview_dir.mkdir(parents=True)
    _write(preview_dir, "index.html", HOME)
    _write(preview_dir, "style.css", ORIGINAL_CSS)
    _write(preview_dir, "script.js", "console.log('home');")
    _write(preview_dir, "_debug_trace.json", "[]")
    (preview_dir / "full").mkdir()
    _write(preview_dir / "full", "stale.html", "<html></html>")

    meta = {
        "site_name": "Acme",
        "colors": {"primary": "#111111", "secondary": "#222222", "accent": "#333333"},
        "fonts": {"heading": "Inter", "body": "Inter"},
    }
    pages = [{"page_url": url} for url in PAGE_URLS]
    (blueprint_dir / "blueprint.json").write_text(
        json.dumps({"meta": meta, "navigation": [], "pages": pages}), encoding="utf-8"
    )
    (project_root / "metadata.json").write_text(
        json.dumps({"assets": [], "source_url": "https://example.com/"}), encoding="utf-8"
    )
    return project_root


def test_generate_full_site_copies_script_js_appends_only_and_enforces_consistency(tmp_path, monkeypatch):
    monkeypatch.setattr(site_generator.tier_service, "is_tier_enabled", lambda key: True)
    project_root = _make_project(tmp_path)
    seen = {}

    def fake_run_agent_loop(settings, model_name, system_prompt, user_message, dispatch, trace_path=None, required_files=()):
        seen["message"] = user_message
        # The agent tries to replace script.js and restyle body -- both must be contained.
        dispatch["write_file"]("script.js", "console.log('about');")
        dispatch["write_file"]("style.css", "body{background:black}\n.about-hero{padding:2rem}")
        for name in required_files:
            dispatch["write_file"](
                name,
                "<html><head><title>p</title></head><body><header><nav>x</nav></header>"
                "<main><h1>p</h1></main><footer>old</footer></body></html>",
            )
        return "done", {"prompt_tokens": 0, "completion_tokens": 0}, 1

    monkeypatch.setattr(site_generator, "_run_agent_loop", fake_run_agent_loop)

    result = site_generator.generate_full_site(project_root, "pro", template_override="business_Industrial_prompt.txt")

    full_dir = project_root / "generated" / "pro" / "full"
    script = (full_dir / "script.js").read_text(encoding="utf-8")
    assert script.startswith("console.log('home');") and "about" in script
    css = (full_dir / "style.css").read_text(encoding="utf-8")
    assert "background:black" not in css and "about-hero" in css
    assert not (full_dir / "stale.html").exists()
    assert not (full_dir / "full").exists()
    assert "site-header" in seen["message"]  # D3: shared chrome handed to the agent
    about = (full_dir / "about-us.html").read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" in about and 'class="site-footer"' in about
    home = (full_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="about-us.html"' in home  # home nav no longer points at the old live site
    assert result["consistency"]["links_rewritten"]
    assert result["consistency"]["css_rules_stripped"]
