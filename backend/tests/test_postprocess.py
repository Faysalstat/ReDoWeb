from pathlib import Path

from app.ai.postprocess import (
    _fix_reveal_visibility_gaps,
    _find_hidden_by_default_classes,
    _find_js_reveal_pairs,
    _has_compound_override,
    postprocess_output,
)

BUGGY_CSS = """
.reveal{opacity:0;transform:translateY(22px);transition:opacity 600ms ease}
.fab.is-visible{opacity:1;visibility:visible;transform:none}
"""

BUGGY_JS = """
(function () {
  var revealItems = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
  var revealObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  });
  revealItems.forEach(function (el) { revealObserver.observe(el); });
})();
"""

FIXED_CSS = BUGGY_CSS + "\n.reveal.is-visible{opacity:1;transform:none}\n"

MINIMAL_HTML = "<html><head><title>Acme</title></head><body><p>hi</p></body></html>"


def test_find_hidden_by_default_classes_detects_opacity_zero_rule():
    assert _find_hidden_by_default_classes(BUGGY_CSS) == {"reveal"}


def test_find_hidden_by_default_classes_ignores_compound_selectors():
    css = ".reveal.is-visible{opacity:0}"
    # ".reveal.is-visible" is a compound selector, not a standalone
    # ".is-visible" rule -- neither class should be flagged as "starts
    # hidden by itself".
    assert _find_hidden_by_default_classes(css) == set()


def test_find_js_reveal_pairs_pairs_nearest_preceding_query_selector():
    hidden = {"reveal"}
    pairs = _find_js_reveal_pairs(BUGGY_JS, hidden)
    assert pairs == {("reveal", "is-visible")}


def test_has_compound_override_true_when_rule_exists():
    assert _has_compound_override(FIXED_CSS, "reveal", "is-visible") is True


def test_has_compound_override_false_when_missing():
    assert _has_compound_override(BUGGY_CSS, "reveal", "is-visible") is False


def test_fix_reveal_visibility_gaps_patches_missing_override(tmp_path: Path):
    (tmp_path / "style.css").write_text(BUGGY_CSS, encoding="utf-8")
    (tmp_path / "script.js").write_text(BUGGY_JS, encoding="utf-8")

    fixes = _fix_reveal_visibility_gaps(tmp_path)

    assert len(fixes) == 1
    assert ".reveal.is-visible" in fixes[0]
    patched_css = (tmp_path / "style.css").read_text(encoding="utf-8")
    assert _has_compound_override(patched_css, "reveal", "is-visible")
    assert "opacity:1 !important" in patched_css


def test_fix_reveal_visibility_gaps_is_a_noop_when_already_correct(tmp_path: Path):
    (tmp_path / "style.css").write_text(FIXED_CSS, encoding="utf-8")
    (tmp_path / "script.js").write_text(BUGGY_JS, encoding="utf-8")

    fixes = _fix_reveal_visibility_gaps(tmp_path)

    assert fixes == []
    assert (tmp_path / "style.css").read_text(encoding="utf-8") == FIXED_CSS


def test_fix_reveal_visibility_gaps_handles_missing_css_or_js(tmp_path: Path):
    # No .css or .js files at all in the output dir -- must not crash.
    assert _fix_reveal_visibility_gaps(tmp_path) == []

    (tmp_path / "style.css").write_text(BUGGY_CSS, encoding="utf-8")
    assert _fix_reveal_visibility_gaps(tmp_path) == []


def test_postprocess_output_reports_and_applies_reveal_fix(tmp_path: Path):
    (tmp_path / "index.html").write_text(MINIMAL_HTML, encoding="utf-8")
    (tmp_path / "style.css").write_text(BUGGY_CSS, encoding="utf-8")
    (tmp_path / "script.js").write_text(BUGGY_JS, encoding="utf-8")

    report = postprocess_output(tmp_path, frontmatter={})

    assert len(report["reveal_visibility_fixes"]) == 1
    patched_css = (tmp_path / "style.css").read_text(encoding="utf-8")
    assert _has_compound_override(patched_css, "reveal", "is-visible")
