"""Curated, code-enforced font library -- real, free, verified Google Fonts
only, spanning the moods the design recipes (backend/prompts/recipes/) and
the blueprint's inferred `tone` actually need. Exists to close a real bug
found via end-to-end testing: both the meta-review call
(blueprint_review.py's Call A, inferring a business's fonts from its logo)
and the design-system call (design_system_generation.py) were free-text
font-name prompts with nothing validating the answer was a real, loadable
font -- verified in practice with a business logo producing the invented
name "Pawtastic" for a heading font, which silently failed to load
(Google Fonts CDN 404s/ignores an unknown family) and fell back to generic
sans-serif.

Both call sites are meant to (a) show the model this list and instruct it
to pick only from it, AND (b) run the result through `normalize_font()`
afterward -- the prompt instruction alone is not trusted, exactly like this
project's other AI-output safety nets (blueprint_review.py's merge
functions, design_system_generation.py's real-colors-always-win
normalization). A model that ignores the instruction and names something
else just gets silently corrected to the given fallback rather than a made
up family ever reaching generated CSS or a Google Fonts <link> tag.

All fonts are loaded via the Google Fonts CDN in generated output (matches
TECH_CONSTRAINTS' existing CDN-friendly approach for Tailwind/Bootstrap) --
self-hosting font files was considered and deliberately not done; nothing
here needs it since every entry is confirmed free and CDN-available.

Two tiers, deliberately not merged: FONT_LIBRARY is what gets shown to the
model for a NEW typography choice (curated for taste, not just realness).
ADDITIONAL_ACCEPTED_FONTS is real-but-not-recommended fonts (Roboto, Open
Sans, etc.) that normalize_font() still accepts so a scraped site's actual
original font -- or a vision call correctly, if unremarkably, identifying
one -- doesn't get wrongly "corrected" away as if it were hallucinated.
"""

# name -> (category, one-line mood/character note). Category groups fonts
# for prompt organization only; a font's actual heading/body role is a
# design-system decision, not fixed here (most sans fonts work as either).
FONT_LIBRARY: dict[str, str] = {
    # Editorial / elegant serif
    "Fraunces": "warm, characterful serif with old-style softness",
    "Newsreader": "highly readable serif, built for long-form body text",
    "Instrument Serif": "refined, quiet display serif",
    "Cormorant Garamond": "elegant, classic, light-touch serif",
    "Playfair Display": "bold, high-contrast editorial serif",
    "DM Serif Display": "bold, confident display serif",
    # Clean geometric / humanist sans
    "Inter": "neutral, extremely readable, dependable body workhorse",
    "Inter Tight": "tighter-tracking Inter variant, strong for headlines",
    "Manrope": "geometric, modern, quietly elegant",
    "Plus Jakarta Sans": "warm geometric sans with friendly rounded terminals",
    "Outfit": "geometric, friendly, versatile",
    "Work Sans": "humanist, versatile, unpretentious",
    "Sora": "geometric, tech-leaning, confident",
    "Space Grotesk": "geometric with distinctive quirks, tech/dev-tool feel",
    # Bold display / grotesque
    "Archivo Black": "heavy, no-nonsense grotesque for short bold headlines",
    "Archivo Expanded": "bold, wide, poster-like presence",
    "Bricolage Grotesque": "playful, bold, variable-weight grotesque",
    "Big Shoulders Display": "condensed, bold, industrial poster feel",
    # Rounded / friendly
    "Quicksand": "rounded, soft, calm and approachable",
    "Baloo 2": "rounded, playful, confidently bold",
    "Nunito": "rounded terminals, friendly, versatile at body sizes",
    "Comfortaa": "rounded, geometric, gentle",
    # Condensed / technical
    "Oswald": "condensed, strong, utilitarian",
    "Archivo Narrow": "condensed, clean, technical",
    # Monospace (accents, code, labels -- not full body/heading use)
    "JetBrains Mono": "technical monospace, excellent legibility",
    "Space Mono": "distinctive monospace with character",
    "IBM Plex Mono": "clean, technical monospace",
    # Script / handwritten accent (sparing use only, never body text)
    "Caveat": "warm handwritten accent, for a single emotional line only",
}

# Additional real, legitimate fonts accepted by normalize_font() but
# deliberately NOT surfaced in font_list_text() -- i.e. not offered to the
# model when it's making a fresh design-system typography *choice* (they
# skew toward generic/overused for that purpose), but still real, loadable
# fonts a scraped site's ORIGINAL branding might genuinely already use, or
# that a vision call might correctly (if unremarkably) identify. Rejecting
# these as if they were hallucinated would be its own false-positive bug --
# seen for real: a meta-review call correctly named "Open Sans" for body
# text while separately hallucinating "Pawtastic" for heading; validating
# against FONT_LIBRARY alone would have wrongly rejected the correct answer
# too.
ADDITIONAL_ACCEPTED_FONTS: tuple[str, ...] = (
    "Open Sans",
    "Roboto",
    "Lato",
    "Montserrat",
    "Poppins",
    "Raleway",
    "Source Sans 3",
    "Noto Sans",
)

DEFAULT_HEADING_FONT = "Inter Tight"
DEFAULT_BODY_FONT = "Inter"


def normalize_font(name: str | None, fallback: str) -> str:
    """Case-insensitive membership check against FONT_LIBRARY plus
    ADDITIONAL_ACCEPTED_FONTS. Returns `fallback` (never raises, never
    passes through an unrecognized name) if `name` is empty or isn't a real
    entry in either set -- callers pass an already-validated value as
    `fallback` (see DEFAULT_HEADING_FONT/DEFAULT_BODY_FONT or an upstream
    normalize_font() result) so this can never itself introduce an invalid
    font."""
    if not name:
        return fallback
    stripped = name.strip().lower()
    for real_name in (*FONT_LIBRARY, *ADDITIONAL_ACCEPTED_FONTS):
        if real_name.lower() == stripped:
            return real_name
    return fallback


def font_list_text() -> str:
    """Renders the library as a compact, prompt-ready enumerated list."""
    return "\n".join(f"- {name} ({mood})" for name, mood in FONT_LIBRARY.items())
