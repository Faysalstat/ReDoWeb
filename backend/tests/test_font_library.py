from app.ai.font_library import (
    DEFAULT_BODY_FONT,
    DEFAULT_HEADING_FONT,
    FONT_LIBRARY,
    font_list_text,
    normalize_font,
)


def test_normalize_font_accepts_exact_match():
    assert normalize_font("Space Grotesk", DEFAULT_HEADING_FONT) == "Space Grotesk"


def test_normalize_font_is_case_insensitive():
    assert normalize_font("space grotesk", DEFAULT_HEADING_FONT) == "Space Grotesk"
    assert normalize_font("SPACE GROTESK", DEFAULT_HEADING_FONT) == "Space Grotesk"


def test_normalize_font_trims_whitespace():
    assert normalize_font("  Inter  ", DEFAULT_HEADING_FONT) == "Inter"


def test_normalize_font_rejects_hallucinated_name():
    """The exact real-world failure this module exists to close: a vision
    call inventing a plausible-but-fake font name for a themed business."""
    assert normalize_font("Pawtastic", DEFAULT_HEADING_FONT) == DEFAULT_HEADING_FONT


def test_normalize_font_falls_back_on_empty_or_none():
    assert normalize_font("", DEFAULT_BODY_FONT) == DEFAULT_BODY_FONT
    assert normalize_font(None, DEFAULT_BODY_FONT) == DEFAULT_BODY_FONT


def test_defaults_are_real_library_entries():
    assert DEFAULT_HEADING_FONT in FONT_LIBRARY
    assert DEFAULT_BODY_FONT in FONT_LIBRARY


def test_font_list_text_mentions_every_font():
    text = font_list_text()
    for name in FONT_LIBRARY:
        assert name in text
