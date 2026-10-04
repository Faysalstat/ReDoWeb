> **Status:** planned 2026-10-04, not yet implemented. Decisions already made: independent DB-free service module + CLI first (admin integration later), Playwright for capture (dev-only dependency).

# Plan: "Website → Design Template" extraction pipeline

## Context

`backend/prompts/*.txt` holds 10 hand-authored design-strategy templates. `site_generator._select_template()` picks one at random as the agent's system prompt (plus `TECH_CONSTRAINTS`). Right now the only way to add a template is to write ~150–500 lines by hand. The user wants a repeatable way to see a good-looking website and turn its *visual style* into a new template for the collection.

Decisions made in this session:
- Build it as an **independent, DB-free service module** with a CLI entry point. The admin panel will wrap it later, so the core logic must not depend on the CLI, the DB, or the queue.
- Use **Playwright** for capture: full-page screenshots plus computed styles. It is a dev/local-only dependency and stays out of the Railway image.

## What the analysis of the existing prompts showed

**Shared anatomy.** Every good template follows this structure, and the pipeline should produce exactly it:
1. `<role>` block, using the "build a brand-new static website from scratch" variant
2. `<design-system>` → `# Design Style: <Name>`
   - Design Philosophy (core DNA, vibe, principles)
   - Design Token System: colors with hex values and roles, typography (Google Fonts, weights, scale, tracking), radius scale, shadow/elevation system, textures
   - Component Stylings: buttons, cards, inputs, nav, plus states
   - Layout Strategy: container, grid, spacing, asymmetry
   - Non-Genericness / Signature Elements (the most important section, because it is what makes a template distinctive)
   - Effects & Animation (easing, durations, micro-interactions)
   - Iconography
   - Responsive Strategy
   - Accessibility, and optionally Anti-Patterns

**Inconsistencies.** These should not be repeated in new templates. Fixing the existing files is a separate, optional follow-up.
- Four files use the wrong `<role>`: `business_simpleweb`, `portfolio_asthetic`, `portfolio_sketch` and `service_playful` say "integrate into an existing codebase… ask the user focused questions". That contradicts headless generation. `TECH_CONSTRAINTS` overrides it, but tokens are wasted and the model gets mixed signals.
- Several files contain React-isms that don't fit plain HTML output: `lucide-react`, `framer-motion`, `tsx` snippets and `StyleWrapper`.
- File naming is inconsistent: `organic_prompts.txt`, `asthetic`, `proffessional`. New files will use `prompt_template_service.build_filename()` (`{category}_{name}_prompt.txt`).
- `drafts/business_Industrial_optimised.txt` (226 lines, compared with 428) shows that a tighter version of the same template works. Target about 200–300 lines.

## Pipeline (6 stages, each writing an inspectable artifact)

All output goes to `backend/template_lab/runs/{slug}-{timestamp}/`. This folder is gitignored, and each stage can be re-run on its own from the previous stage's artifact.

| # | Stage | Kind | Output |
|---|---|---|---|
| 1 | **Capture**: Playwright loads the URL at desktop 1440px and mobile 390px. It takes a full-page screenshot plus per-section crops (top-level `section`/`header`/`footer`/`main > *`, or about 1200px slices as a fallback). It also samples computed styles for `body`, `h1–h3`, `p`, `a`, `button`, `input`, `nav`, and card-like elements (font-family/size/weight/letter-spacing/line-height, color, background, border-radius, box-shadow, transition), reads `:root` CSS custom properties and Google Fonts `<link>`s, and detects frameworks (Tailwind classes, Bootstrap). | deterministic | `capture/*.png`, `capture/styles.json` |
| 2 | **Token distillation**: frequency-rank colors and assign roles (bg, fg, primary, accent, muted, border), find font pairs, and cluster radius, shadow and spacing scales. | deterministic | `tokens.json` |
| 3 | **Style analysis**: a vision call with the section screenshots and `tokens.json`. It returns strict JSON: style name, philosophy, vibe references, signature elements, layout patterns, component treatments, motion, anti-patterns. It must describe the *style only*: no brand name, copy, industry or logo. Templates are applied to other businesses' content. | AI (vision) | `style_analysis.json` |
| 4 | **Template authoring**: a text call that receives `tokens.json`, `style_analysis.json` and one existing template as a format exemplar, and writes the template in the canonical anatomy above. The `<role>` block is **not** generated: code inserts the canonical "from scratch" role block verbatim. | AI (text) | `template.txt` |
| 5 | **Lint**: checks that all required sections are present, that there are at least 5 hex colors and named Google Fonts, and that there are no React-isms (`lucide-react`, `framer-motion`, `tsx`, `className=`). It flags any leak of the source brand (site name, domain or `<title>` tokens appearing in the text) and enforces the `MAX_UPLOAD_BYTES` size cap. | deterministic | `lint_report.json` |
| 6 | **Promote**: copy the file to `backend/prompts/drafts/{category}_{name}_prompt.txt`. | deterministic | draft file |

**Human loop after stage 6:**
1. Trial-render with the existing debug route (`routers/debug_pipeline.py`, `template_override="drafts/<file>.txt"`). This works today because `_select_template()`'s override only checks `is_relative_to(PROMPTS_DIR)`, and `glob("*.txt")` is non-recursive, so drafts are never picked at random.
2. Edit by hand if needed.
3. Move the file into `backend/prompts/` (or upload it through the admin page). It then goes live via `prompt_template_service`.

## Files

New package: `backend/app/template_extraction/` (DB-free; plain functions that take paths and return dicts)
- `capture.py`: Playwright capture (stage 1). Imports Playwright lazily, so the backend still imports without it installed.
- `tokens.py`: distillation (stage 2). Reuses `_normalize_hex`, `_is_neutral` and `_hex_to_rgb` from `app/ai/color_extraction.py`. Promote these to public names if needed.
- `analyze.py`: stage 3 via `openrouter_client.vision_json_chat()` (it already handles downscaling, JSON mode and retries).
- `author.py`: stage 4 via `openrouter_client.chat_completion()`. Also holds `CANONICAL_ROLE_BLOCK`, copied verbatim from `business_Industrial_prompt.txt` lines 1–22.
- `lint.py`: stage 5.
- `pipeline.py`: `run_extraction(url, out_dir, *, category, name, vision_model=None, text_model=None, from_stage=1) -> dict`. This is the single entry point the admin task will call later.
- `prompts/`: the system prompts for stages 3 and 4, kept as files.
- `__main__.py`: CLI, `python -m app.template_extraction <url> --category business --name glassmorphism [--from-stage 3] [--model ...]`.

Other changes:
- `backend/requirements-dev.txt` (new, or an existing dev file if there is one): `playwright`, with a note to run `playwright install chromium`. Do **not** add it to `requirements.txt`, which builds the Railway image.
- `.gitignore`: `backend/template_lab/runs/`
- `docs/template-extraction-pipeline.md`: the workflow, the canonical anatomy, and the review checklist.
- `docs/PROGRESS.md`: one entry.

Reuse:
- `prompt_template_service.sanitize_template_name()`/`build_filename()` for naming
- `PROMPTS_DIR` from `site_generator`
- `vision_json_chat`/`chat_completion` from `openrouter_client`
- `settings.crawler_user_agent` for Playwright's user agent

Guardrails:
- Respect `robots.py`'s `check_robots_allowed()` before capture.
- The stage-3 and stage-4 prompts must explicitly forbid copying the source's text, logos, imagery or brand identity. Only abstract style is extracted. Stage 5's leak check enforces this in code.

## Later admin integration (not in this pass)

- A `template_extract` queue task that calls `pipeline.run_extraction()`.
- `POST /api/v1/admin/template-extractions` and a status endpoint.
- A preview of the lint report and template text in the admin Prompt Templates page, with an "approve" action that goes through `save_uploaded_template()`.
- Railway would then need Chromium in the image. That decision is deferred.

## Verification

- **Unit tests** (deterministic parts only, following the CLAUDE.md testing bar):
  - `tokens.py` on a fixed `styles.json` fixture
  - `lint.py`: rejects a template that is missing sections, contains `lucide-react`, or contains the source site's brand name; accepts `business_Industrial_optimised.txt`-style input
  - `author.py`: the role block is always the canonical one, even if the fake LLM response includes its own
- **Manual run** (you trigger it; I'll set up the command): `python -m app.template_extraction https://<site> --category business --name test --model openai/gpt-4o-mini`. Inspect `runs/.../capture/*.png`, `tokens.json` and `lint_report.json`.
- **Trial render**: call the debug generate route with `template_override=drafts/business_test_prompt.txt` on an existing project, then compare the output with the reference site's look.
