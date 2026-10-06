# Buy flow, all-pages build and SEO agent (Pro & Premium)

## Context

The generation flow has two parts:
- **Before purchase:** only the home page is generated, as the preview.
- **After purchase:** for a multi-page site, the remaining pages are built from the saved `blueprint.json`/`design.md`. That build reuses the preview's `template_used`, keeps `index.html` locked and keeps `style.css` append-only, so the design stays identical (`tasks_full_site.generate_full_site_task`). The task itself is unchanged. Today it starts automatically inside the combined charge-and-download call (`POST /projects/{id}/download`); this plan splits that into **Buy**, followed by explicit **Download**, **Generate all pages** and **Run SEO agent** buttons.

The user wants a third step for **purchased Pro/Premium tiers: a "Run SEO" button** that starts an agentic SEO pass over the finished site, whether that's the full multi-page site or the single page. It is **included in the purchase**: it runs once, and a retry is allowed only if it failed. The download then delivers the SEO-optimized version.

**What exists today:** only the deterministic net in [postprocess.py](backend/app/ai/postprocess.py), which runs on every tier. It does three things:
- fills in missing alt text with words taken from the image filename;
- injects OG tags with a relative `og:url`;
- writes `sitemap.xml` with the placeholder domain `REPLACE-WITH-YOUR-DOMAIN.com`.

There is no robots.txt, canonical link, meta description, JSON-LD, heading check, link check, image optimization or llms.txt. Full-site pages are named `page-N.html`.

**Decisions:**
- **Buy is its own action** (user decision, revised 2026-10-05). Buying a tier's design unlocks three separate buttons: **Download ZIP**, **Generate all pages** and **Run SEO agent**. Before purchase, all three are shown disabled with a lock icon.
- Generate all pages and Run SEO are user-clicked and included in the price. Each runs once, with a retry allowed only after a failure.
- Pro and premium are hardcoded (`SEO_TIER_KEYS`).
- The real domain is the URL the user submitted (more below).

## End-to-end user flow

1. Preview: home page only (unchanged).
2. **Buy design · N credits** spends credits once per (project, tier). It keeps the same `download_spend:{project}:{tier}` ledger key, so **every existing purchase stays valid** and nothing needs migrating. It no longer auto-starts anything.
3. After purchase, the three buttons are enabled:
   - **Download ZIP**: always available. It serves the best output that exists right now: SEO version, then full site, then preview.
   - **Generate all pages** (shown only when `page_count > 1`): starts the existing `generate_full_site_task`, which uses the same design (pinned template, locked `index.html`, append-only CSS).
   - **Run SEO agent** (Pro/Premium only): on a multi-page site it stays **disabled until all pages are generated** ("Generate all pages first"), so SEO always runs on the final site and a later page build can't leave an outdated SEO copy behind. On a single-page site it's enabled straight after purchase.
4. Builds run in the background and the UI polls. Download stays usable throughout and serves whatever is best so far.

## Design consistency for the all-pages build (reviewed 2026-10-05)

**Requirement (user):** every page built by "Generate all pages" must match the first page's design. When `design.md` is managed properly this should already hold; where it doesn't, fix it first.

**What already holds:**
- **`design.md` is managed correctly.** `tasks_full_site` merges the reviewed remaining pages into `blueprint.json`, but `meta` (`site_name`, `colors`, `fonts`, `logo`, `tone`) always comes from the home blueprint (`_merge_full_blueprint`). `render_design_md_compat` writes exactly those fields into the frontmatter, so the full-site run gets the **same colors, fonts and logo** as the preview.
- **The same design template** is used (the preview's `template_used` is pinned, never re-rolled).
- **`index.html` is copied verbatim and locked**, so the agent can't rewrite it, and `style.css` is append-only.

**Gaps found (confirmed in `site_generator.generate_full_site`), and the fix for each:**

| # | Gap | Effect | Fix |
|---|---|---|---|
| D1 | Only `index.html` and `style.css` are copied into `full/`. **`script.js`** and any other local CSS/JS/favicon files from the preview are not | Every page that references `script.js` gets a 404, or the agent writes a *new* `script.js`, which `index.html` then loads. That can change the home page's behavior, and with the scroll-reveal pattern it can blank out sections | Copy **every** file from the preview directory into `full/`, excluding `full/`, `seo/`, `images/` (copied separately) and debug traces. Lock `script.js` as append-only, the same as `style.css` |
| D2 | Appending to `style.css` doesn't protect the existing styles: a later `body{}`, `h1{}`, `:root{}` or a repeated `.btn{}` **overrides** the home page's rules, because CSS cascade order lets the last matching rule win | New pages can change the look of the home page and of each other | New `postprocess.guard_appended_css(original_css, final_css)` checks only the appended part. It **strips** rules whose selector targets bare elements (`html, body, :root, *, h1–h6, p, a, img, ul, li, button, input, section, header, footer, nav, main`) or repeats a selector already in the original stylesheet, then writes the cleaned file and lists each stripped rule in the report. The prompt already says "only new component classes"; this enforces it |
| D3 | The model is *told* to read `index.html` first, but nothing makes it | A batch that skips the read invents its own head, nav and footer | Put the home page's shared markup directly in each batch's user message: its `<head>` assets (stylesheets, fonts, CDN scripts, inline Tailwind config) and its `<header>`/`<nav>`/`<footer>` markup. These are pulled out by code with BeautifulSoup, so the model always has them |
| D4 | No check that new pages load the same assets | A page missing the Tailwind CDN, `tailwind.config` or the Google Fonts link renders in a different font and style | New `postprocess.enforce_shared_head(index_html, page_html)` runs after all batches. It adds any stylesheet link, font/preconnect link, `script src` or inline config script from the home page's `<head>` that a page is missing, and never removes anything. Reported |
| D5 | Nav and footer can drift between pages | Inconsistent menus and footers | After the internal links are rewritten (breakage item 5a), new `postprocess.sync_site_chrome()` replaces each page's top-level `<footer>` with the home page's, and its `<nav>` (or `<header>`) with the home page's **when the home page's header has no `<h1>`/hero inside it**. That check keeps a page's own hero safe. Reported |
| D6 | The full-site run uses the tier's *current* generation model; an admin may have changed it since the preview | A different model can interpret the same template differently | Resolve the preview job's model from its `TokenUsageLog` (`purpose="generation"`, `job_id=preview_job.id`) and pass it to `generate_full_site`. Fall back to the current tier model when no log exists |

**Order inside `generate_full_site` after the agent batches:**
1. `rewrite_internal_links` (item 5a)
2. `enforce_shared_head`
3. `sync_site_chrome`
4. `guard_appended_css`
5. the existing `postprocess_output`

All of these steps are deterministic and covered by unit tests.

## Purchase gating (also a security fix)

Today `GET /download-file` never checks payment; only `POST /download` charges. Every post-purchase endpoint (download-file, full-site, seo) will now check `_is_purchased(db, project, tier)`, which looks for a ledger row with `download_spend_key(project.id, tier)`, and return **403 "Buy this design first"** if it's missing.

## Real domain instead of the placeholder (every tier)

`crawl_service` already saves the submitted URL as `"source_url"` in `metadata.json`, and `generate_site()`/`generate_full_site()` already read that file.
- `site_origin_from_url()` turns it into `https://{netloc}`.
- That origin is passed to `postprocess_output()`, so the sitemap and an absolute `og:url` use the real domain for **every tier**, Basic included.
- The placeholder is only a fallback when `source_url` is missing or can't be parsed.
- The SEO pass uses the same origin for canonical links, OG/Twitter, robots.txt and llms.txt.

## How the SEO pass works: audit, then agent, then finalize

- **Works on a copy and never changes what's already delivered.** The source (`generated/{tier}/full/` when a full-site job succeeded, otherwise `generated/{tier}/`, leaving out the `full/`, `seo/` and `_debug_trace*` entries) is copied to `generated/{tier}/seo/`, and every edit happens there. If the run fails, the previous output is still downloadable.
1. **Audit (code):** finds missing or too-long titles and descriptions, the `<h1>` count, skipped heading levels, broken internal links and anchors, weak alt text, `noindex` tags and `http://` links.
2. **Agent:** gets the blueprint, the audit findings, and the page → canonical URL map. It fixes the items that need judgment, using **constrained tools**: `read_file`, `list_files`, and a new `edit_file(path, old, new)` that requires an exact, unique match. `write_file` may only create *new* files and cannot overwrite `.html/.css/.js`. This is enforced in code: the agent can't redesign the site, and with no full-page rewrites the truncation risk goes away.
3. **Finalize (code, idempotent):** handles the mechanical items and the files, re-audits, and saves the before/after results in `GenerationOutput.seo_report`.

If the agent fails, the job is marked `failed` and the user can retry. Downloads keep serving the previous output.

## The 20-point checklist, mapped

| # | Check | How | Owner |
|---|---|---|---|
| 1 | sitemap.xml | Real https origin, `<lastmod>`, index mapped to `/` | Code |
| 2 | robots.txt | `User-agent: *` / `Allow: /` / `Sitemap: {origin}/sitemap.xml` | Code |
| 3 | Remove noindex | Strip `noindex`/`nofollow` from robots and googlebot meta tags | Code |
| 4 | Canonical | Absolute `<link rel="canonical">` on every page | Code |
| 5 | Meta titles | Under about 60 chars, unique, brand plus main service | Agent; checked by code |
| 6 | Meta descriptions | 120–160 chars from blueprint copy, unique | Agent; checked by code |
| 7 | One H1 | Change tag names only, keep classes; code re-checks | Agent + code |
| 8 | Heading order | No skipped levels, appearance unchanged | Agent |
| 9 | Alt text | Descriptive alt; decorative images get `alt=""` | Agent |
| 10 | Schema | JSON-LD `Organization`/`LocalBusiness` + `WebSite`, plus `FAQPage` when FAQs exist, **using only blueprint facts**. Code drops JSON that doesn't parse and strips any `telephone/email/address` not found in the blueprint `contact`. It also strips `aggregateRating`, `review`, `offers`, `priceRange` and `award` whenever the blueprint has no matching testimonials, pricing or credentials, because those are the most common fabricated schema fields | Agent + code |
| 11 | Internal links | Contextual links between pages, and better text for vague links like "click here" | Agent |
| 12 | Broken links | The audit finds local hrefs, srcs and anchors that don't resolve; the agent fixes them; code re-checks | Code + agent |
| 13 | Compress images | Pillow (already a dependency): max width 1920, JPEG q≈82, optimized PNG, **same filenames** | Code |
| 14 | Core Web Vitals | `<img>` `width`/`height` from the real file size, `loading="lazy"` + `decoding="async"` on everything except the hero, `fetchpriority="high"` on the hero, `preconnect` for font and CDN hosts, `defer` on local scripts. The Tailwind CDN stays render-blocking because the no-build-tooling decision is settled | Code |
| 15 | Mobile layout | Make sure the `viewport` meta exists. Real layout fixes need visual rendering and are out of scope; the agent is told not to restyle | Code (partial) |
| 16 | HTTPS | All absolute URLs use https; rewrite same-origin `http://` links and report mixed content. The redirect itself is a hosting setting and is noted in `SEO-NEXT-STEPS.md` | Code (partial) |
| 17 | Clean URL slugs | `_page_output_filename` produces slugs from the crawled path (`/about-us/` → `about-us.html`): only `[a-z0-9-]`, a `-2` suffix on collisions, and a `page-N` fallback. This affects new full-site builds | Code |
| 18 | og:image | Absolute logo URL, falling back to the hero image; also `og:site_name` and `twitter:*` | Code |
| 19 | Search Console | `SEO-NEXT-STEPS.md` in the zip: verify the domain, submit the sitemap, set up the HTTPS redirect | Code (doc) |
| 20 | llms.txt | Site name, tagline, and `## Pages` with `- [Title](url): description` taken from the final pages | Code |

Also handled: `<html lang>`, `<meta charset>`, and the favicon link from `meta.favicon`.

## Backend changes

**New**
- `backend/app/ai/seo_agent.py`
  - `SEO_TIER_KEYS = frozenset({"pro", "premium"})`
  - `site_origin_from_url()`
  - `run_seo_pass(output_dir, *, blueprint, site_origin, generation_model)`: audit, then `_run_agent_loop` with the SEO tools, `required_files=()` and `trace_path=output_dir/"_debug_trace_seo.json"` (the zip already excludes `_debug_trace*.json`), then finalize. Returns `{report, usage, iterations, model, summary}`.
- `backend/app/ai/seo_postprocess.py`: `audit_seo()`, `finalize_seo()`, `optimize_images()`, `write_llms_txt()`, `write_next_steps()`.
- `backend/prompts/seo/seo_agent_prompt.md`: the agent's instructions (items 5–12), the no-fabrication rule, "edit_file only, never change classes, layout or copy beyond SEO". It goes in a subdirectory because `_select_template()` and `prompt_template_service` only glob `prompts/*.txt` at the top level, so it can't be picked as a design template.
- `backend/app/workers/tasks_seo.py`: `run_seo_task(project_id, tier, job_id)` follows the same pattern as `generate_full_site_task`: the job row already exists, and the task never touches `Project.status`.
  1. Resolve the source (succeeded full-site output, otherwise the preview output).
  2. Copy it to `generated/{tier}/seo/` using `_rmtree_with_retry` for the clear.
  3. Load `blueprint.json` and the origin from `metadata.json`, then call `run_seo_pass`.
  4. Add a `GenerationOutput` with `seo_report`, and call `token_usage_service.record_usage(purpose="seo")`.
  5. Mark the job succeeded, or failed with a reason.
- An Alembic migration adding `generation_outputs.seo_report` (JSONB, nullable).
- Tests: `test_seo_postprocess.py`, `test_seo_tools.py`, plus decision-function tests in `test_downloads.py`. There are no router tests: `Project` uses Postgres-only INET, so it can't run on SQLite, and the existing pure-function pattern is used instead.

**Modified**
- [downloads.py](backend/app/routers/downloads.py), reorganized around Buy plus three post-purchase actions. All of them keep the ownership check and the active-tier check.
  - **`POST /projects/{id}/purchase?tier=`** (replaces `POST /download`): the existing `wallet_service.spend(... download_spend_key ...)` call and the structured 402 shortfall body, moved unchanged. It is idempotent (buying again costs nothing) and **no longer enqueues a full-site build**. Returns `{purchased: true}`.
  - `GET /projects/{id}/download-file?tier=`: adds the purchase gate (403). Serves the newest succeeded `seo` output, then `full_site`, then `preview`.
  - **`POST /projects/{id}/full-site?tier=`**: purchase gate, then 400 when `page_count <= 1`, then the existing Project-row `FOR UPDATE` race guard. If a job is `running`, return running. If one `succeeded`, return 409 "already built". If one `failed` or none exists, create a `scope="full_site"` job and `enqueue("generate_full_site", …)`. This is the job-creation code moved from today's `start_download`, and `generate_full_site_task` itself is unchanged.
  - **`POST /projects/{id}/seo?tier=`**: purchase gate, then `tier in SEO_TIER_KEYS` (otherwise 400), then on a multi-page site the full-site job must have succeeded (otherwise 409 "Generate all pages first"), then the same lock and running/succeeded/failed rules with `enqueue("run_seo", …)`.
  - Pure, unit-testable decision functions replace `_resolve_download_plan`: `_resolve_full_site_action(page_count, job)` and `_resolve_seo_action(tier, page_count, full_site_job, seo_job)`.
  - `GET /download-status` is removed. `POST /download` stays as a deprecated alias for purchase that returns `{status: "ready"}` and never auto-builds (see breakage item 3).
- [download_service.py](backend/app/services/download_service.py): `write_site_zip(..., excluded_dirs=())`. `build_download_zip` excludes the `full/` and `seo/` subdirectories (breakage item 1).
- [schemas/project.py](backend/app/schemas/project.py) + [routers/projects.py](backend/app/routers/projects.py): the project detail response gets `page_count` and `tier_actions: {tier: {full_site_status, seo_status, seo_available, failure_reason}}`, where each status is `none|running|succeeded|failed`. This lets the buttons render the right state on load and while polling, with no extra status endpoints. It is computed from the latest `full_site`/`seo` `GenerationJob` per tier.
- [schemas/download.py](backend/app/schemas/download.py): `PurchaseResponse` and `ActionStartResponse {status: "running"}`; the old download start/status models are removed.
- [queue_worker.py](backend/app/workers/queue_worker.py): register `"run_seo": run_seo_task` next to `generate_full_site`.
- [generation_tools.py](backend/app/ai/generation_tools.py): `EDIT_FILE_SCHEMA`, `SEO_TOOL_SCHEMAS`, and `make_seo_tool_dispatch()`, reusing `_resolve_safe_path`.
- [site_generator.py](backend/app/ai/site_generator.py):
  - `_run_agent_loop` gets `tool_schemas=TOOL_SCHEMAS` (it's hardcoded at line 518 today);
  - `_page_output_filename` produces slugs;
  - `generate_site`/`generate_full_site` derive `site_origin` from `metadata["source_url"]` and pass it to `postprocess_output`.
- [postprocess.py](backend/app/ai/postprocess.py): the `site_origin` param drives the sitemap domain and an absolute `og:url`. Also a new `rewrite_internal_links(output_dir, url_to_filename)` (breakage item 5a), called by `generate_full_site()` after its batches and before `postprocess_output`, with the map built from `blueprint.pages` and `_page_output_filenames`.
- [models/job.py](backend/app/models/job.py): `GenerationOutput.seo_report`, and a `scope` comment adding `"seo"`.
- No changes to `tasks_generate.py`: there's no SEO at preview time.

## Frontend changes (UI)

**API layer** ([redowebs-api.service.ts](frontend/src/app/core/redowebs-api.service.ts), `redowebs-api.models.ts`):
- add `purchaseTier()`, `startFullSite()`, `startSeo()`, and keep `downloadFile()`;
- remove `startDownload()`/`getDownloadStatus()`;
- add `page_count` and `tier_actions` to `ProjectStatusResponse`.

**Tier card in the "ready" view** ([generation-progress.component.html](frontend/src/app/features/generation/generation-progress.component.html), `gp-topbar__actions` plus a new strip under the top bar). For the selected tier:

```
NOT PURCHASED
  [Start over]                                   [Buy design · 5 credits]
  ┌ Unlocks with purchase ─────────────────────────────────────────────┐
  │ 🔒 Download ZIP   🔒 Generate all 8 pages   🔒 Run SEO agent         │
  └────────────────────────────────────────────────────────────────────┘
  (the three are disabled appButtons; tooltip "Buy this design to unlock")

PURCHASED  (badge: "Purchased ✓")
  [Start over]                                           [Download ZIP]
  ┌ Your design ───────────────────────────────────────────────────────┐
  │ ✓ Home page          [Generate all 8 pages]        [Run SEO agent] │
  │   ZIP contains: Home page only / All 8 pages / All pages + SEO      │
  └────────────────────────────────────────────────────────────────────┘
```

**Button states:**
- **Buy design:** "Buy design · N credits" → "Buying…". On a 402 it shows the existing top-up box, whose copy changes to "Buying the X design needs…".
- **Generate all pages:** shown only when `page_count > 1`.

  | State | Label | Enabled |
  |---|---|---|
  | none | "Generate all N pages" | yes |
  | running | "Generating pages…" + spinner | no |
  | succeeded | "All N pages generated ✓" | no |
  | failed | "Retry generating pages", with the reason in red underneath | yes |

- **Run SEO agent:** shown only when `tier_actions[tier].seo_available` is true. The backend's `SEO_TIER_KEYS` is the only source of truth, so the frontend has no duplicate tier list.

  | State | Label | Enabled |
  |---|---|---|
  | multi-page site, pages not generated yet | "Run SEO agent", hint "Generate all pages first" | no |
  | none | "Run SEO agent" | yes |
  | running | "Optimizing for search…" | no |
  | succeeded | "SEO optimized ✓" | no |
  | failed | "Retry SEO", with the reason | yes |

- **Download ZIP:** always enabled once purchased, including while a build runs. The "ZIP contains" caption says what the download will hold right now.

**Component logic** ([generation-progress.component.ts](frontend/src/app/features/generation/generation-progress.component.ts)):
- Replace the `download()` flow (`DownloadState`, `pollDownload`) with:
  - `buy(tier)`, which calls `purchaseTier`, marks the tier paid and refreshes the wallet;
  - `download(tier)`, which goes straight to `fetchFile`;
  - `generateAllPages(tier)` and `runSeo(tier)`.
- Action state comes from `status().tier_actions`. After starting an action, or on load when any action is already `running`, start a separate `actionPollSubscription` that polls until no tier action is `running`. Don't reuse `startPolling`: it stops at the terminal `ready` status (breakage item 2).
- Top-up return URL: `?buy=<tier>` resumes the **purchase** (replacing `?download=`). `?download=<tier>`, which the History page still links to, triggers an automatic download only when the tier is already purchased.
- [history.component.html](frontend/src/app/features/history/history.component.html): no change. Its "Download" link for purchased tiers still works through `?download=`.

## Breakage review (2026-10-05): what this plan could break, and the fix built into it

I checked every caller of the code this plan touches. Each item below was confirmed in the code, and each fix is part of the plan.

**Would break, so it must be fixed:**
1. **The ZIP would include half-built folders.** `download_service.write_site_zip` walks the output directory recursively (`rglob`), and the preview output directory `generated/{tier}/` is the *parent* of `full/` and `seo/`. Download is now enabled while builds run, so a home-page-only download could pick up an in-progress `full/` or `seo/`. **Fix:** `write_site_zip` gets `excluded_dirs` and `build_download_zip` passes `{"full", "seo"}`. Unit test in `test_download_service.py`.
2. **Polling would stop immediately.** In the frontend, `startPolling` uses `takeWhile(!TERMINAL_STATUSES.has(status))`, and project status `ready` is terminal, so restarting it after clicking Generate all pages or Run SEO would fetch once and stop. **Fix:** a separate `actionPollSubscription` that polls `getProjectStatus` and runs `takeWhile(anyTierActionRunning(res))`. It feeds the same `handleStatus`, which I checked is safe to re-run while `ready`: `selectedTier` is only set when null, preview URLs are cached, and `stopLiveIndicators` is idempotent. It doesn't restart ticking. It is unsubscribed in `ngOnDestroy`.
3. **Old browser tabs would hit a missing endpoint.** A tab still running the old frontend calls `POST /download`, which would return 404 after deploy. **Fix:** keep `POST /download` as a thin deprecated alias for purchase that returns `{status: "ready"}` and never auto-builds. Drop `GET /download-status`; only the old poll calls it, and that poll treats an error as `failed`.
4. **History "Download" links could hit a 403.** `?download=<tier>` resume now calls `download()` directly. **Fix:** only auto-download when `isPurchased(tier)`; otherwise just select the tier, so the Buy button is visible.

5a. **Home-page nav points to the old live site** (confirmed in `blueprint_legacy_compat._render_body`). The preview's nav is rendered from the crawled site's own hrefs (`- About (https://site.com/about-us)`), and the full-site build keeps that `index.html` locked for the agent. So the delivered full site's home nav links back to the **original live site** instead of `about-us.html`. This affects every tier, Basic included. **Fix (code, no AI):** after `generate_full_site()`'s agent batches, a new `postprocess.rewrite_internal_links(output_dir, url_to_filename)` normalizes every `<a href>` on every page (absolute, root-relative and relative; ignoring trailing slash, `index.html`, `#fragment`, `www.`, and http vs https) against the crawled page URL → slug filename map, and rewrites matches to the local file (keeping any `#fragment`). It runs as code, so the agent-only lock on `index.html` doesn't apply, and it touches only `href` values, never markup or styles. External and unmatched links are left alone. It is applied **only in `full/`**, never to the preview `index.html`: until the other pages exist, linking to them would create broken links.

**Could change the design, so it's guarded:**
5. **`width`/`height` on `<img>` can stretch images** when hand-written CSS sets `width:100%` without `height:auto`. **Fix:** append `:where(img[width][height]){height:auto}` to the SEO copy's stylesheet. It has zero specificity, so any class-based height or `object-fit` rule still wins, but it overrides the presentational size hint. Tailwind's preflight already does the same. **When the page links no local stylesheet** (for example, Tailwind CDN only), inject the same rule as a `<style data-seo-guard>` block at the end of `<head>`. The marker keeps the step idempotent.
6. **`defer` on scripts can break inline scripts** that call functions from `script.js`. **Fix:** only defer local scripts when the page has no other inline `<script>` (JSON-LD excluded). Never touch CDN scripts; the Tailwind CDN plus inline `tailwind.config` must stay synchronous.
7. **Retagging headings changes appearance** when CSS styles bare `h1{}`/`h2{}` elements. Keeping classes isn't enough. **Fix:** the audit computes `heading_retag_safe` per page. It is true only when no local stylesheet or inline `<style>` has bare element rules for those heading levels **and** the page doesn't load a CDN framework that styles headings globally. Bootstrap's CDN stylesheet sizes `h1`–`h6` directly, and the check can't read it, so any `bootstrap` CSS link (and Bulma, Foundation and similar) makes the page unsafe. Tailwind CDN pages usually qualify, because its preflight resets headings. When it's false, the agent may not change heading tags; it only reports them, and the problem stays in `seo_report` as a warning.
8. **Internal links:** the agent may only wrap an *existing* phrase in an `<a>` (a few per page). It may not add new blocks or text.
9. **Image compression:** skip SVG and animated GIF, wrap each image in try/except so a corrupt file is skipped rather than failing, keep the same filename and format, and only touch the `seo/` copy.

**Checked and safe as planned:**
- **Cost estimates:** `cost_estimation_service._calibration_samples` filters `purpose == "generation"`, so SEO usage must be logged as `purpose="seo"` (as planned) or preview cost estimates would skew.
- **Other scope filters:** `generation_status_service` and `projects.py` filter `scope == "preview"`, so `seo` jobs never affect project status or the preview tabs. Admin project detail shows `job.scope` as raw text, so `seo` shows up correctly. Admin success-rate stats will count SEO jobs (acceptable). `GenerationJob.scope` is `String(16)`, which fits `"seo"`.
- **`retry-tier`** wipes `generated/{tier}/` (including `full/` and `seo/`) but only runs for a *failed* preview, and a failed preview can't be purchased.
- **Existing purchases:** the same `download_spend` ledger key and reason means `purchased_download_tiers`, the History "Paid" badges and earlier purchases all keep working. Already-built `full/` outputs keep their `page-N` names; slugs apply to new builds only.
- **Earlier output is untouched:** SEO works on a copy, so `generated/{tier}/` and `full/` stay as they are. The SEO pass does **not** lock `index.html` in its copy, because fixing the home page's nav links is a main job of the broken-link check (item 12) and edits are limited to small snippets via `edit_file`.
- **Disk space:** `tasks_seo` calls `check_free_disk_space()` before copying, as `tasks_generate` does.
- **Disabled tiers:** all new endpoints keep the existing `tier_info.is_active` check, the same behavior `download_file` has today.
- **Existing tests:** `generate_site`/`generate_full_site` don't pass `tool_schemas`, so the test fakes of `_run_agent_loop` (`test_site_generator.py`) still match. Tests to update: `test_site_generator.py` (the `page-N` assertion), `test_downloads.py` (`_resolve_download_plan` is replaced), and possibly `test_tasks_full_site.py` (it uses `page_url=/page-{i}` URLs, which now slug to `page-1.html`, the same as before).

## Open questions and follow-ups

- **Settled: no rerun of "Generate all pages" for now** (user decision, 2026-10-05). It runs once per purchase, with a retry only after a *failure*. A build that succeeds but looks wrong is handled as a support request, not a self-serve rerun. The D1–D6 consistency fixes are what keep that from being needed.
- **Settled: the preview stays single-page (home page only)** (user decision, 2026-10-05). There's no page picker for `full/` or `seo/`; the user sees the full site in the downloaded ZIP.
- **Settled: SEO unlock rules.** Run SEO is only available after purchase. On a multi-page site it unlocks **only after Generate all pages succeeds**. On a single-page site it unlocks right after purchase, because the preview already is the full site.

## Deferred: per-project tier pricing (excluded 2026-10-05)

Pricing each tier from a predicted cost (scraped size, page count, SEO) was planned and then **dropped from this scope** at the user's request, because it raised too many pricing problems:
- the gate amount didn't match the Buy price;
- the $1 gate would fire for most multi-page sites, even for new users;
- the preview would have been charged twice;
- the fallback estimates weren't measured yet.

For this plan:
- **Buy price stays the flat admin-set `Tier.download_credit_cost`**, the same as today.
- **The existing preview cost gate (`tasks_blueprint._apply_cost_gate`, `approve-generation`) is unchanged.**
- No `tier_quotes` column, no `price_markup` setting, and no change to `cost_estimation_service`.

Revisit as its own plan once real `full_site_generation`/`seo` token history exists to calibrate against.

## Docs

Update the CLAUDE.md settled-decisions bullets. A new SEO bullet covers: after purchase, user-triggered, included once, Pro/Premium hardcoded, the `seo/` sibling directory, and the audit/agent/finalize split. The generation bullet changes from `page-N` to slug names. Add an entry to `docs/PROGRESS.md`.

## Reused

`_run_agent_loop`, `_rmtree_with_retry`, `_copy_images` (not needed, because the copy brings `images/`), `_resolve_safe_path`, `BlueprintDocument`, `model_config_service.get_generation_model`, `token_usage_service.record_usage`, `wallet_service.download_spend_key`, the queue `enqueue`/worker dispatch, the Project row-lock race guard from `start_download`, and the zip's `_debug_trace*.json` exclusion.

## Verification

- Unit tests (deterministic only):
  - `edit_file` rejects a missing match, an ambiguous match, path traversal and locked files, and `write_file` can't overwrite `.html`;
  - the finalizer adds a canonical link, https OG, robots.txt, a sitemap with the real origin, llms.txt and SEO-NEXT-STEPS, and strips `noindex`;
  - invalid JSON-LD is dropped, a fabricated phone is stripped, and an invented `aggregateRating`/`offers` is stripped when the blueprint has no testimonials or pricing;
  - `heading_retag_safe` is false for a page that links the Bootstrap CDN;
  - the image-size guard is injected as `<style data-seo-guard>` when there's no local stylesheet, and only once;
  - broken links are detected;
  - images are recompressed under the same name and get `width`/`height`;
  - slugs handle collisions;
  - design consistency:
    - `guard_appended_css` strips appended `body{}`/`h1{}` and repeated-selector rules but keeps new component classes;
    - `enforce_shared_head` adds a missing Tailwind CDN, config or font link and never removes anything;
    - `sync_site_chrome` replaces the nav and footer, but leaves a header that contains an `<h1>` alone;
    - `generate_full_site` copies `script.js` into `full/` and makes it append-only;
  - `rewrite_internal_links`: absolute, root-relative, trailing-slash, `www.` and http variants of a crawled URL all map to the slug file; `#fragment` is kept; external and unmatched links are untouched; nothing other than `href` changes;
  - running the finalizer twice adds no duplicates;
  - `site_origin_from_url` works;
  - decision functions: `_resolve_full_site_action` (single page gives 400; running, succeeded and failed each give the right result), `_resolve_seo_action` (Basic tier gives 400, multi-page site without pages gives 409, a second run after success gives 409, a retry after failure is allowed), and a pure helper for the download output preference (SEO, then full site, then preview);
  - replace the old `_resolve_download_plan` tests in `tests/test_downloads.py`;
  - `test_download_service.py`: the preview ZIP excludes the `full/` and `seo/` subdirectories;
  - guard rails: the `:where(img…){height:auto}` rule is appended once; `defer` is skipped when an inline script exists; `heading_retag_safe` is false when the CSS has a bare `h1{` rule;
  - update the `page-N` assertion in `tests/test_site_generator.py`.
- Manual (the user triggers it):
  1. Run `alembic upgrade head`, then restart the API and the worker.
  2. Before buying: all three buttons are locked, and `GET /download-file` returns 403.
  3. Generate a multi-page site and buy Pro. Download right away (home page only), then click Generate all pages. While it runs, Run SEO stays locked with "Generate all pages first"; once it finishes, click Run SEO.
  4. Inspect `generated/pro/seo/`: head tags, robots.txt, sitemap with the real domain, llms.txt, slugged pages, and `_debug_trace_seo.json`.
  5. Download the zip and check that home-page nav links go to the local slug pages, not the old live site.
  6. Check that `generated/pro/` and `full/` are untouched and the pages look the same.

## Implementation progress (2026-10-05)

**All steps implemented**; not yet exercised end-to-end against a real model (that's the manual verification above).

- Design consistency (D1–D6, item 5a): `app/ai/site_consistency.py` (a separate module rather than more functions in `postprocess.py`), wired into `site_generator.generate_full_site`; `tasks_full_site` pins the preview's model and stores `consistency_report`.
- Slug page filenames: `site_generator._page_output_filename` / `_page_output_filenames`.
- SEO: `generation_tools.make_seo_tool_dispatch`, `app/ai/seo_postprocess.py`, `app/ai/seo_agent.py` (includes the heading-retag restore backstop), `prompts/seo/seo_agent_prompt.md`, `workers/tasks_seo.py`, `run_seo` in `queue_worker.py`.
- Real domain for every tier: `postprocess.site_origin_from_url` / `page_url`.
- API: `services/tier_actions_service.py`; `routers/downloads.py` (purchase, full-site, seo, gated download-file, deprecated `/download` alias; `/download-status` removed); project status `page_count` + `tier_actions`; `download_service` excludes nested `full/`/`seo/`.
- DB: migration `f3b9d2a7c1e4` (`seo_report`, `consistency_report`).
- Frontend: API service/models, Buy button, locked/unlocked action strip, action polling, `?buy=`/`?download=` resume, `IconLock`.
- Tests: 481 backend passing. `ng build` passes with two budget warnings (initial bundle 508 kB vs 500 kB; generation-progress CSS 8.4 kB vs 8 kB). The component CSS was already at 9 kB raw before this change.
- Docs: CLAUDE.md (new Buy-flow and SEO bullets, updated full-site bullet) and PROGRESS.md.
- **Progress and run logs (added 2026-10-06):** `services/job_progress.py` + `generation_jobs.progress` (migration `a7c3e9f1b5d2`), `_run_agent_loop(on_event=…)`, step and activity reporting in `seo_agent`/`tasks_seo`, `tier_actions[tier].seo_progress` for users (progress bar, then the run log), and the full log on the admin project page.
