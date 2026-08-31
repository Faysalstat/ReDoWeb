# Structured JSON Blueprint Pipeline (scraped.json → blueprint.json)

Status: **Approved, implementation in progress.** Persisted here (separate from the ephemeral Claude Code plan-mode file) so it survives across sessions per this project's working style — see [PROGRESS.md](PROGRESS.md) for milestone tracking.

## Context

Today's blueprint stage (`backend/app/ai/blueprint_extractor.py`) produces a single semi-structured `design.md` (YAML frontmatter + freeform markdown body), built from heuristic HTML parsing plus two OpenRouter calls that only check 4 fixed content sections (About, Services, CTA, FAQ) for gaps. This makes review/regeneration hard to reason about (freeform prose, no fixed shape) and limits gap-filling to a narrow slice of the site.

The new direction: define one canonical JSON schema covering the sections a modern small-business website actually has (16 keys total: `meta`, `navigation`, plus 14 per-page sections). The crawler/extraction stage maps scraped HTML + already-downloaded images into this schema deterministically (no AI) as `scraped.json` — every key always present, empty when the source site lacks it. An AI review stage then walks `scraped.json` and produces `blueprint.json` in the **exact same schema shape**: correcting section placement, improving weak copy, and filling empty *Mandatory* sections with tone-matched, fact-grounded copy — while *Optional* (fabrication-risk) sections stay untouched/empty if the source lacked them, enforced in code, not just prompted.

This plan covers extraction + review only. Generation (`app/ai/site_generator.py`) is explicitly out of scope — a separate follow-up plan will rewire it to consume `blueprint.json` directly, and for now it will only build the home page (per user decision), with additional pages generated later as a paid feature. To keep the app working end-to-end in the meantime, this plan also writes a deterministic (no-AI) compatibility `design.md` at the same fixed path `site_generator.py` already reads.

## Schema (Mandatory vs Optional)

**Mandatory** (review drafts content if the source site lacks it — safe since it's marketing copy, not a factual claim): `meta` (text fields only — see below), `navigation` (structurally derived, never drafted), `hero`, `about`, `services_features`, `faq`, `cta_section`, `footer` (structurally derived, never drafted).

**Optional / no-fabrication** (left empty if the source lacks it — review must NEVER populate these, enforced in code): `testimonials`, `gallery_portfolio`, `team`, `pricing`, `stats_social_proof`, `credentials_awards`, `contact`, `blog_news`.

All image-reference fields (logo, favicon, hero.background_image, about.image, services_features[].icon_image, gallery_portfolio[].image, team[].photo, credentials_awards[].badge_image) hold **only** the existing project-root-relative `storage_path` string already produced by `crawler/assets.py` (e.g. `snapshot/image/ab12cd34-logo.png`) — never a full asset object, never fabricated. These are heuristic/extraction-only fields; the AI review calls never see or touch them (enforced by what's included in each call's request/response shape, not by prompt instruction alone).

## New modules (replace `backend/app/ai/blueprint_extractor.py`)

- **`backend/app/ai/blueprint_schema.py`** — pure Pydantic models, the shared contract for both `scraped.json` and `blueprint.json` (`BlueprintDocument` = `meta: MetaBlock`, `navigation: list[NavLink]`, `pages: list[PageBlueprint]`; `PageBlueprint` = `page_url: str` + `sections: PageSections` holding all 14 section keys with safe empty defaults so every key survives `model_dump()`).
- **`backend/app/ai/blueprint_extraction.py`** (no LLM calls) — `extract_scraped_json(project_root: Path) -> BlueprintDocument`. Reads `metadata.json` + page HTML exactly as today; reuses unchanged: `_guess_site_name`, `color_extraction.py`, `DEFAULT_COLORS`/`DEFAULT_FONTS`, email/phone regexes. New logic: `_segment_page` (DOM segmentation on h1-h3 boundaries), `_classify_blocks` (positional hero + keyword-haystack matching per section type, footer always structurally derived from `<footer>`), a repeated-sibling structural pass for list-typed sections, and `_assign_images` (generalizes `_guess_logo_asset`'s technique to all 8 image fields). **Critical invariant**: an asset URL not present in `metadata.json`'s already-downloaded assets list must never be assigned.
- **`backend/app/ai/blueprint_review.py`** (AI half) — `review_blueprint(project_root, scraped) -> tuple[BlueprintDocument, dict]`. Call A (meta, ×1, vision if logo exists, degrades gracefully to heuristic fallbacks on failure — supersedes today's fail-hard rule since every meta text field now has a working fallback). Call B (content, ×1 per page, ≤3 total, text-only, reviews only the 5 Mandatory text-bearing sections, degrades to unreviewed scraped sections on failure). Merge is code-enforced: only the 5 allowed Call-B keys are ever read off the response, image sub-fields always come from scraped data regardless of model output, and `navigation`/`footer`/all 8 Optional sections are copied byte-for-byte, never sent to any LLM call.
- **`backend/app/ai/blueprint_legacy_compat.py`** — `render_design_md_compat(blueprint) -> str`, pure/deterministic adaptation of today's markdown-rendering helpers, producing YAML-frontmatter + body from `BlueprintDocument` instead of the old flat content list.
- **`backend/app/ai/blueprint_pipeline.py`** (orchestration entry point) — `run_blueprint_pipeline(project_root) -> dict`. Fixed paths, always overwritten (no versioned subfolders — matches today's behavior, avoids breaking `site_generator.py`'s hardcoded path): writes `blueprint/scraped.json`, `blueprint/blueprint.json`, `blueprint/design.md`.

`blueprint_extractor.py` is deleted once the above is in place.

## Data layer changes

- **`backend/app/models/blueprint.py`**: unchanged `id, project_id, version, source, is_current, created_at`; denormalized `site_name`/`colors`/`fonts`/`tone`/`logo_path` now sourced from `blueprint.json`'s `meta` block (no read-side ripple elsewhere); add `tagline`, `favicon_path`, `scraped_json_storage_path`, `blueprint_json_storage_path`; relax `design_md_storage_path` to nullable.
- **Alembic migration**: new file, `down_revision = 'c69f2b03d8a1'` (confirmed current head — no other migration references it as a parent).
- **`backend/app/schemas/blueprint.py`**: delete `ColorPalette`/`Fonts`/`Frontmatter` (superseded), redesign `BlueprintResponse` to `{project_id, version, scraped_json_path, blueprint_json_path, design_md_path, blueprint: BlueprintDocument, usage}`.
- **`backend/app/routers/blueprint.py`** and **`backend/app/workers/tasks_blueprint.py`**: both call `run_blueprint_pipeline(project_root)`, build the `Blueprint` row from `result["blueprint"]["meta"]` plus the new storage-path columns.

## Verification (matches project's confirmed testing bar — crawler/AI quality is manual, not e2e-tested)

**New unit tests** (cheap, deterministic logic only): schema round-trip/key-presence; `_segment_page`/`_classify_blocks` fixtures; `_assign_images` never fabricates a path for an undownloaded asset (most important test); Call-B merge function silently drops smuggled Optional/image-field content.

**Manual verification checklist**, run against real crawled sites: schema validation on both JSON files; every non-null image path exists on disk; hero/about/services/faq bucketing plausibility; Optional sections stay empty end-to-end; Mandatory sections read as tone-matched fact-grounded copy after review; `site_generator.py` still runs end-to-end via the compat `design.md`; project/admin read endpoints unaffected.

## Explicitly out of scope

`app/ai/site_generator.py` / the generation pipeline — a separate follow-up plan will rewire it to consume `blueprint.json` directly and scope output to the home page only.

### Critical files
- `backend/app/ai/blueprint_extractor.py` (deleted)
- `backend/app/ai/blueprint_schema.py`, `blueprint_extraction.py`, `blueprint_review.py`, `blueprint_legacy_compat.py`, `blueprint_pipeline.py` (new)
- `backend/app/models/blueprint.py`
- `backend/app/schemas/blueprint.py`
- `backend/app/routers/blueprint.py`
- `backend/app/workers/tasks_blueprint.py`
- `backend/alembic/versions/` (new migration)
