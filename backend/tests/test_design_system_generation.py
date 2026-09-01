import pytest

from app.ai import design_system_generation
from app.ai.blueprint_schema import (
    BlueprintDocument,
    ColorPalette,
    Fonts,
    HeroSection,
    MetaBlock,
    PageBlueprint,
    PageSections,
)
from app.ai.design_system_generation import (
    DEFAULT_CANDIDATES,
    build_fallback_design_system,
    generate_design_system,
    select_candidate_recipes,
)
from app.ai.errors import OpenRouterError


def _make_blueprint(tone: str = "", colors: dict | None = None, fonts: dict | None = None) -> BlueprintDocument:
    colors = colors or {"primary": "#123456", "secondary": "#abcdef", "accent": "#ff0000"}
    fonts = fonts or {"heading": "Real Heading Font", "body": "Real Body Font"}
    return BlueprintDocument(
        meta=MetaBlock(
            site_name="Acme Co",
            tagline="We build things",
            colors=ColorPalette(**colors),
            fonts=Fonts(**fonts),
            tone=tone,
        ),
        pages=[
            PageBlueprint(
                page_url="https://acme.example.com/",
                sections=PageSections(hero=HeroSection(headline="Welcome to Acme")),
            )
        ],
    )


# --- select_candidate_recipes -------------------------------------------


def test_select_candidate_recipes_matches_distinctive_keyword():
    result = select_candidate_recipes("corporate and professional")

    assert result[0] == "linear"


def test_select_candidate_recipes_falls_back_on_empty_tone():
    assert select_candidate_recipes("") == list(DEFAULT_CANDIDATES)
    assert select_candidate_recipes(None) == list(DEFAULT_CANDIDATES)


def test_select_candidate_recipes_falls_back_on_no_keyword_match():
    assert select_candidate_recipes("xyzxyz totally unmatched") == list(DEFAULT_CANDIDATES)


def test_select_candidate_recipes_respects_limit():
    result = select_candidate_recipes("warm friendly playful colorful", limit=2)

    assert len(result) <= 2


def test_select_candidate_recipes_is_deterministic_across_calls():
    assert select_candidate_recipes("industrial and rugged") == select_candidate_recipes(
        "industrial and rugged"
    )


# --- build_fallback_design_system ---------------------------------------


def test_build_fallback_design_system_uses_real_colors_and_fonts():
    spec = build_fallback_design_system(
        colors={"primary": "#111111", "secondary": "#222222", "accent": "#333333"},
        fonts={"heading": "Space Grotesk", "body": "Work Sans"},  # real FONT_LIBRARY entries
        tone="corporate",
    )

    assert spec["colors"]["primary"] == "#111111"
    assert spec["colors"]["secondary"] == "#222222"
    assert spec["colors"]["accent"] == "#333333"
    assert spec["typography"]["heading"] == "Space Grotesk"
    assert spec["typography"]["body"] == "Work Sans"
    assert spec["recipe_anchor"] == "linear"


def test_build_fallback_design_system_never_raises_on_missing_data():
    spec = build_fallback_design_system(colors={}, fonts={}, tone="")

    assert spec["colors"]["primary"]
    assert spec["typography"]["heading"]
    assert spec["recipe_anchor"] in design_system_generation._RECIPE_KEYWORDS


def test_build_fallback_design_system_respects_explicit_anchor():
    spec = build_fallback_design_system(colors={}, fonts={}, recipe_anchor="industrial-craft")

    assert spec["recipe_anchor"] == "industrial-craft"


def test_build_fallback_design_system_rejects_hallucinated_font():
    spec = build_fallback_design_system(colors={}, fonts={"heading": "Pawtastic", "body": "Open Sans"})

    assert spec["typography"]["heading"] != "Pawtastic"
    from app.ai.font_library import FONT_LIBRARY

    assert spec["typography"]["heading"] in FONT_LIBRARY
    assert spec["typography"]["body"] == "Open Sans"  # a real library font passes through unchanged


# --- generate_design_system (AI step + degrade path) ---------------------


def test_generate_design_system_degrades_to_fallback_on_openrouter_error(monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths):
        raise OpenRouterError("boom")

    monkeypatch.setattr(design_system_generation, "vision_json_chat", fake_vision_json_chat)

    blueprint = _make_blueprint(tone="corporate and professional")
    spec, usage = generate_design_system(blueprint)

    assert spec["colors"]["primary"] == "#123456"
    assert spec["recipe_anchor"] == "linear"
    assert usage == {}


def test_generate_design_system_never_lets_model_override_real_colors(monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths):
        return (
            {
                "recipe_anchor": "aesop",
                "colors": {
                    "primary": "#fabricated1",
                    "secondary": "#fabricated2",
                    "accent": "#fabricated3",
                    "derivation_rule": "hover = +10% lightness",
                },
                # "Newsreader" is a real, valid FONT_LIBRARY entry -- this
                # test is specifically about colors, so the typography pick
                # must be one the model is allowed to keep (see the
                # separate hallucinated-font test below for the rejection
                # path).
                "typography": {"heading": "Newsreader", "body": "Work Sans", "notes": "n"},
            },
            {"prompt_tokens": 5, "completion_tokens": 5},
        )

    monkeypatch.setattr(design_system_generation, "vision_json_chat", fake_vision_json_chat)

    blueprint = _make_blueprint(colors={"primary": "#123456", "secondary": "#abcdef", "accent": "#ff0000"})
    spec, usage = generate_design_system(blueprint)

    assert spec["colors"]["primary"] == "#123456"
    assert spec["colors"]["secondary"] == "#abcdef"
    assert spec["colors"]["accent"] == "#ff0000"
    assert spec["colors"]["derivation_rule"] == "hover = +10% lightness"
    assert spec["typography"]["heading"] == "Newsreader"
    assert spec["recipe_anchor"] == "aesop"
    assert usage == {"prompt_tokens": 5, "completion_tokens": 5}


def test_generate_design_system_rejects_hallucinated_font_from_model(monkeypatch):
    """Locks in the exact real-world failure this feature closes: the model
    naming a plausible-but-fake font ("Pawtastic") that would otherwise
    silently fail to load in generated CSS."""

    def fake_vision_json_chat(system_prompt, user_text, image_paths):
        return (
            {"recipe_anchor": "mailchimp-freddie", "typography": {"heading": "Pawtastic", "body": "Open Sans"}},
            {},
        )

    monkeypatch.setattr(design_system_generation, "vision_json_chat", fake_vision_json_chat)

    blueprint = _make_blueprint(fonts={"heading": "Inter Tight", "body": "Inter"})
    spec, _usage = generate_design_system(blueprint)

    assert spec["typography"]["heading"] != "Pawtastic"
    assert spec["typography"]["heading"] == "Inter Tight"  # falls back to the (already-real) meta font
    assert spec["typography"]["body"] == "Open Sans"  # a real library font passes through unchanged


def test_generate_design_system_falls_back_to_candidate_when_anchor_missing(monkeypatch):
    def fake_vision_json_chat(system_prompt, user_text, image_paths):
        return {}, {}

    monkeypatch.setattr(design_system_generation, "vision_json_chat", fake_vision_json_chat)

    blueprint = _make_blueprint(tone="industrial and rugged")
    spec, _usage = generate_design_system(blueprint)

    assert spec["recipe_anchor"] == "industrial-craft"
    # Typography falls back to the real (if unimpressive) extracted fonts
    # when the model returns nothing usable, rather than inventing one.
    assert spec["typography"]["heading"] == "Real Heading Font"


def test_generate_design_system_respects_explicit_candidates_override(monkeypatch):
    captured = {}

    def fake_vision_json_chat(system_prompt, user_text, image_paths):
        captured["user_text"] = user_text
        return {"recipe_anchor": "vibrant-friendly"}, {}

    monkeypatch.setattr(design_system_generation, "vision_json_chat", fake_vision_json_chat)

    blueprint = _make_blueprint(tone="corporate")
    generate_design_system(blueprint, candidates=["vibrant-friendly"])

    assert "Candidate recipe: vibrant-friendly" in captured["user_text"]
    assert "Candidate recipe: linear" not in captured["user_text"]
