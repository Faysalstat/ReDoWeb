"""AI step that turns a reviewed blueprint's real brand data into a
concrete, project-specific design-system spec -- the "web-design-engineer"
skill's Design Read + Five Dials and Declare-the-design-system steps
(agent/SKILL.md, Steps 2b/3), performed as one JSON-producing OpenRouter
call instead of an interactive back-and-forth, since the generation
pipeline runs headless with no user turn available.

Anchored against a small curated recipe library (backend/prompts/recipes/,
adapted from agent/references/style-recipes/ plus two custom recipes for
verticals that library doesn't cover) rather than invented from nothing --
the skill itself is explicit that AI design quality collapses without a
concrete reference to anchor to.

Runs once per project (not once per tier) in blueprint_pipeline.py, right
after review_blueprint() -- every enabled tier's generation call shares the
same design_system.json. Degrades the same way blueprint_review.py's meta
call does: on OpenRouterError, falls back to a deterministic spec built
from the real extracted colors/fonts plus the top keyword-matched recipe,
so a failed call never fails the whole pipeline.

The real, deterministically-extracted brand colors (color_extraction.py --
no LLM involved) always win over anything the model echoes back for them;
the model is only trusted to state a derivation *rule* for dependent shades
(hover/muted/etc.), not to precompute hex math itself -- the generated CSS
applies that rule with real oklch()/relative-color-syntax, so a small AI
arithmetic slip never matters. Fonts are the opposite: the model's pick is
kept even when it differs from the site's original fonts, since typography
is the lowest-priority brand-recognition signal and this product's premise
is modernizing the site, not reproducing its (often generic) original type
-- but the pick itself is constrained to font_library.py's curated,
verified Google Fonts list and code-enforced via normalize_font(), the same
way blueprint_review.py's meta call is, since a free-text font name has
genuinely hallucinated a plausible-but-fake font in practice.

Future hook, not built yet: tier-specific "dial" variance (visual variance/
motion/density/asset-dependence/brand-fidelity, per agent/SKILL.md's Five
Dials) would slot in here as an optional per-tier nudge on top of the same
shared spec, once Basic/Premium reactivate (tier_service currently has only
`pro` active) -- not worth the added complexity for a single active tier.
"""

import re
from pathlib import Path

from .blueprint_schema import BlueprintDocument
from .errors import OpenRouterError
from .font_library import DEFAULT_BODY_FONT, DEFAULT_HEADING_FONT, font_list_text, normalize_font
from .openrouter_client import vision_json_chat

RECIPES_DIR = Path(__file__).resolve().parents[2] / "prompts" / "recipes"

# Keyword -> recipe name, used to pre-filter the ~10 recipes down to a small
# candidate set before the AI call ever sees them, keeping its context
# small and bounded rather than feeding every recipe into every call.
# Grounded in each recipe file's own stated vibe/best-for language -- kept
# in sync with the keyword column in recipes/INDEX.md.
_RECIPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "linear": ("corporate", "professional", "trust", "trusted", "trustworthy", "enterprise", "business", "saas", "polished", "serious"),
    "vercel-mesh": ("modern", "sleek", "dark", "tech", "technical", "minimal", "minimalist"),
    "aesop": ("warm", "premium", "refined", "quiet", "artisan", "boutique"),
    "muji-kenya-hara": ("calm", "calming", "natural", "minimal", "handcrafted", "quiet"),
    "apple-hig": ("premium", "polished", "confident", "sophisticated", "clean"),
    "pentagram": ("bold", "confident", "graphic", "direct", "strong"),
    "mailchimp-freddie": ("friendly", "warm", "approachable", "fun", "personal", "playful"),
    "headspace-meditation": ("calm", "caring", "gentle", "cozy", "welcoming", "soothing"),
    "industrial-craft": ("industrial", "technical", "mechanical", "rugged", "precise", "functional", "engineering"),
    "vibrant-friendly": ("vibrant", "colorful", "playful", "fun", "dynamic", "expressive"),
}

# A broad, safe spread (professional / refined / friendly) used whenever
# `tone` is empty or matches no keyword -- never returns an empty list.
DEFAULT_CANDIDATES = ("linear", "aesop", "mailchimp-freddie")

DESIGN_SYSTEM_SYSTEM_PROMPT = (
    "You are a design director translating a small business's real brand "
    "data into a concrete design-system specification for a static "
    "marketing homepage. You will be shown the business's real, "
    "already-extracted brand colors, fonts, name/tagline, overall tone, "
    "and which content sections its site actually has -- plus 2-3 "
    "candidate style recipes to anchor your decisions in.\n\n"
    "Pick the single best-fitting recipe, or explicitly blend two of them, "
    "as your anchor -- do not invent a look with no stated anchor. The "
    "recipe's example colors/fonts are illustrative only: resolve every "
    "color decision around the REAL primary/secondary/accent colors given "
    "below (substitute them for the recipe's example hex values, keeping "
    "the recipe's relationships -- which role appears where, how "
    "sparingly an accent is used, ground vs. surface vs. accent). Do not "
    "feel bound to the site's original fonts if a better pairing fits the "
    "chosen recipe -- typography is the lowest-priority brand-recognition "
    "signal, real colors and the logo (already handled elsewhere) matter "
    "far more, and the goal is a modernized design, not a literal clone. "
    "Pick your heading and body fonts ONLY from this exact list (never the "
    "site's original font name unless it happens to appear here, never a "
    "name outside this list):\n"
    f"{font_list_text()}\n\n"
    "For color derivation, state a RULE (e.g. 'hover = +8% lightness, "
    "muted = -15% chroma') rather than precomputing hex values yourself -- "
    "the generated CSS will apply your rule with real oklch()/"
    "relative-color-syntax math, so it can't be wrong.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown fences) in "
    "this exact shape:\n"
    '{"recipe_anchor": string, "visual_language": string, '
    '"colors": {"derivation_rule": string}, '
    '"typography": {"heading": string, "body": string, "notes": string}, '
    '"spacing_scale": string, "radius_strategy": string, '
    '"shadow_style": string, "motion_style": string, '
    '"layout_guidance": string}'
)


def select_candidate_recipes(tone: str, limit: int = 3) -> list[str]:
    """Deterministically scores `tone` (free text, may be empty) against
    each recipe's keyword set and returns up to `limit` names, best-matched
    first. Falls back to DEFAULT_CANDIDATES (never empty) when `tone` is
    empty or matches nothing -- the safety net that keeps the AI call from
    ever having zero anchors to work from, and keeps generate_design_system
    working even before a meta-review call has ever populated `tone`."""
    words = set(re.findall(r"[a-z]+", (tone or "").lower()))
    if not words:
        return list(DEFAULT_CANDIDATES)

    scored = []
    for name, keywords in _RECIPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in words)
        if score > 0:
            scored.append((score, name))

    if not scored:
        return list(DEFAULT_CANDIDATES)

    # Stable, deterministic tie-break: highest score first, then by the
    # table's own insertion order (dicts preserve it) rather than anything
    # that could vary between runs.
    order = {name: index for index, name in enumerate(_RECIPE_KEYWORDS)}
    scored.sort(key=lambda pair: (-pair[0], order[pair[1]]))
    return [name for _, name in scored[:limit]]


def _load_recipe_text(name: str) -> str:
    return (RECIPES_DIR / f"{name}.md").read_text(encoding="utf-8")


def _section_presence(blueprint: BlueprintDocument) -> list[str]:
    """Which of the named section types have real content on any page --
    a cheap, deterministic signal (no LLM needed) for the kind of business
    this looks like (e.g. pricing + testimonials suggests professional
    services; gallery_portfolio with no pricing suggests a creative/
    portfolio business)."""
    present: set[str] = set()
    for page in blueprint.pages:
        sections = page.sections
        if sections.hero.headline:
            present.add("hero")
        if sections.about.body:
            present.add("about")
        if sections.services_features:
            present.add("services_features")
        if sections.faq:
            present.add("faq")
        if sections.testimonials:
            present.add("testimonials")
        if sections.gallery_portfolio:
            present.add("gallery_portfolio")
        if sections.team:
            present.add("team")
        if sections.pricing:
            present.add("pricing")
        if sections.stats_social_proof:
            present.add("stats_social_proof")
        if sections.credentials_awards:
            present.add("credentials_awards")
        if sections.blog_news:
            present.add("blog_news")
    return sorted(present)


def _build_user_message(blueprint: BlueprintDocument, candidates: list[str]) -> str:
    meta = blueprint.meta
    recipes_text = "\n\n".join(
        f"--- Candidate recipe: {name} ---\n{_load_recipe_text(name)}" for name in candidates
    )
    return (
        "Real brand data:\n"
        f"- site_name: {meta.site_name}\n"
        f"- tagline: {meta.tagline}\n"
        f"- tone: {meta.tone or '(not determined)'}\n"
        f"- colors: primary={meta.colors.primary}, secondary={meta.colors.secondary}, accent={meta.colors.accent}\n"
        f"- fonts (site's original, low-priority signal): heading={meta.fonts.heading}, body={meta.fonts.body}\n"
        f"- content sections present: {', '.join(_section_presence(blueprint)) or '(none detected)'}\n\n"
        f"{recipes_text}"
    )


def build_fallback_design_system(
    colors: dict, fonts: dict, tone: str = "", recipe_anchor: str | None = None
) -> dict:
    """Deterministic, no-LLM design-system spec -- used when the AI call
    fails (matches blueprint_review.py's meta-call degrade pattern) or when
    design_system.json is missing at generation time for any other reason.
    Not a full-quality substitute for the AI call, just enough of a
    coherent system that generation never has to invent one from nothing."""
    if recipe_anchor is None:
        candidates = select_candidate_recipes(tone, limit=1)
        recipe_anchor = candidates[0] if candidates else DEFAULT_CANDIDATES[0]

    return {
        "recipe_anchor": recipe_anchor,
        "visual_language": f"Fallback default anchored to the '{recipe_anchor}' recipe.",
        "colors": {
            "primary": colors.get("primary", "#333333"),
            "secondary": colors.get("secondary", "#f5f5f5"),
            "accent": colors.get("accent", "#0066cc"),
            "derivation_rule": "hover = +8% lightness, muted = -15% chroma (apply via CSS oklch()/relative-color-syntax)",
        },
        "typography": {
            "heading": normalize_font(fonts.get("heading"), DEFAULT_HEADING_FONT),
            "body": normalize_font(fonts.get("body"), DEFAULT_BODY_FONT),
            "notes": "Fallback pairing -- prefer the anchor recipe file's own typography guidance when read directly.",
        },
        "spacing_scale": "4 / 8 / 16 / 24 / 40 / 64 / 96",
        "radius_strategy": "moderate, 8-16px on cards and inputs",
        "shadow_style": "soft, single-layer, neutral",
        "motion_style": "200ms ease-out on hover, no bounce",
        "layout_guidance": f"Read backend/prompts/recipes/{recipe_anchor}.md for section composition and signature moves.",
    }


def _normalize_spec(result: dict, blueprint: BlueprintDocument, candidates: list[str]) -> dict:
    """Code-enforced safety net, same spirit as blueprint_review.py's merge
    functions: the real extracted colors always win over anything the
    model echoes back for them, and a malformed/missing field never crashes
    generation -- it falls back to real blueprint data or a sane default."""
    meta = blueprint.meta
    if not isinstance(result, dict):
        result = {}

    colors_in = result.get("colors") if isinstance(result.get("colors"), dict) else {}
    typography_in = result.get("typography") if isinstance(result.get("typography"), dict) else {}

    recipe_anchor = result.get("recipe_anchor")
    if not isinstance(recipe_anchor, str) or not recipe_anchor.strip():
        recipe_anchor = candidates[0]

    return {
        "recipe_anchor": recipe_anchor,
        "visual_language": result.get("visual_language") or "",
        "colors": {
            # Real, deterministically-extracted brand colors always win --
            # the model is trusted only for the derivation-rule text, never
            # for the base hex values themselves.
            "primary": meta.colors.primary,
            "secondary": meta.colors.secondary,
            "accent": meta.colors.accent,
            "derivation_rule": colors_in.get("derivation_rule")
            or "hover = +8% lightness, muted = -15% chroma (apply via CSS oklch()/relative-color-syntax)",
        },
        "typography": {
            # meta.fonts.{heading,body} are themselves already normalized
            # against FONT_LIBRARY (blueprint_review.py), so this fallback
            # is always a real font even if the model's pick isn't.
            "heading": normalize_font(typography_in.get("heading"), meta.fonts.heading),
            "body": normalize_font(typography_in.get("body"), meta.fonts.body),
            "notes": typography_in.get("notes") or "",
        },
        "spacing_scale": result.get("spacing_scale") or "4 / 8 / 16 / 24 / 40 / 64 / 96",
        "radius_strategy": result.get("radius_strategy") or "moderate, 8-16px on cards and inputs",
        "shadow_style": result.get("shadow_style") or "soft, single-layer, neutral",
        "motion_style": result.get("motion_style") or "200ms ease-out on hover, no bounce",
        "layout_guidance": result.get("layout_guidance") or "",
    }


def generate_design_system(
    blueprint: BlueprintDocument, candidates: list[str] | None = None
) -> tuple[dict, dict]:
    """The AI step: reads the reviewed blueprint's real brand data plus 2-3
    keyword-matched candidate recipes, and asks the model to resolve a
    concrete design-system spec anchored in one (or a blend) of them.
    Returns (spec, usage). Called once per project from
    blueprint_pipeline.run_blueprint_pipeline(), right after
    review_blueprint() -- every enabled tier's generation call reads the
    same resulting design_system.json.

    `candidates` overrides the deterministic keyword pre-filter -- real
    callers never pass this (kept at its default None); it exists for
    manually testing one specific recipe via the
    /api/v1/debug/design-system route (the call still goes through the AI
    step, just anchored on a forced candidate list instead of `tone`)."""
    meta = blueprint.meta
    if candidates is None:
        candidates = select_candidate_recipes(meta.tone)
    user_text = _build_user_message(blueprint, candidates)

    try:
        result, usage = vision_json_chat(DESIGN_SYSTEM_SYSTEM_PROMPT, user_text, [])
    except OpenRouterError:
        colors = {"primary": meta.colors.primary, "secondary": meta.colors.secondary, "accent": meta.colors.accent}
        fonts = {"heading": meta.fonts.heading, "body": meta.fonts.body}
        fallback = build_fallback_design_system(colors, fonts, meta.tone, recipe_anchor=candidates[0])
        return fallback, {}

    return _normalize_spec(result, blueprint, candidates), usage
