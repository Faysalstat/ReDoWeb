# Blueprint Pipeline — Manual Verification Experiment

**Status: experimental, disposable.** This is a separate testing/experiment log for validating the new scraped.json → blueprint.json pipeline stage by stage. It does not modify and is not part of [blueprint-json-pipeline-plan.md](blueprint-json-pipeline-plan.md) (the architecture/build plan) or [PROGRESS.md](PROGRESS.md) (the milestone tracker) — those stay as the authoritative build docs. Once the pipeline is validated this way, fold any confirmed findings back into those, or discard this file.

## How to test — via the API (recommended)

Three new **database-free debug endpoints** (`backend/app/routers/debug_pipeline.py`) let you test each stage independently through Swagger UI, with just a URL — no Postgres, Redis, or Celery worker needed, no `project_id` to look up beforehand.

**1. Start the backend:**
```bash
cd backend
./venv/Scripts/python.exe -m uvicorn app.main:app --port 8123
```

**2. Open Swagger UI:** http://localhost:8123/docs — the three endpoints are tagged **`debug-pipeline`**.

---

### Stage 1 — Scraper (free, no AI, no API key needed)

**`POST /api/v1/debug/scrape`**

Body:
```json
{ "url": "https://some-small-business-site.com" }
```

Crawls that URL and runs the deterministic extractor. Response:
```json
{
  "project_id": "a52f2b82-...",
  "scraped": { "meta": {...}, "navigation": [...], "pages": [...] }
}
```

**Copy the `project_id`** from the response — you'll need it for Stage 2. The full `scraped` JSON is also right there in the response body to inspect immediately; it's additionally saved to `backend/storage_data/projects/{project_id}/blueprint/scraped.json` on disk.

**Check:**
1. Every one of the 16 top-level / 14 per-page section keys is present (guaranteed by the schema — just confirm nothing looks structurally off).
2. Every non-null image path (`logo`, `favicon`, `hero.background_image`, etc.) actually exists under `backend/storage_data/projects/{project_id}/`.
3. `hero` / `about` / `services_features` / `faq` / `cta_section` bucketing looks plausible against the real homepage. Try a few different real small-business sites here — the heuristic's quality is what you're actually evaluating in this stage.
4. Optional/no-fabrication sections (`testimonials`, `team`, `pricing`, `stats_social_proof`, `credentials_awards`, `contact`, `blog_news`, `gallery_portfolio`) are empty if the real site doesn't have that content, populated if it does.

Don't move to Stage 2 until this looks right across a few sites — Stage 2 trusts Stage 1's bucketing as its starting point.

---

### Stage 2 — Review (real OpenRouter calls, billed)

**`POST /api/v1/debug/review/{project_id}`**

Path parameter: the `project_id` from Stage 1. No body. Requires `REDOWEBS_OPENROUTER_API_KEY` set in `backend/.env` — unlike Stage 1, this makes real, billed model calls.

Response:
```json
{ "project_id": "a52f2b82-...", "blueprint": {...}, "usage": {"prompt_tokens": N, "completion_tokens": N} }
```

Also saved to `blueprint/blueprint.json` on disk.

**Check:**
1. Every Mandatory section that was empty/weak in `scraped.json` now reads as tone-matched, fact-grounded copy in `blueprint.json`.
2. **Every Optional section empty in `scraped.json` is still empty in `blueprint.json`** — the single most important thing to check every run.
3. Image fields are byte-identical to `scraped.json` — review never touches them.
4. `meta.site_name` / `tagline` / `fonts` / `tone` read sensibly against the real logo/brand.

---

### Stage 3 — Generation (validates backward compatibility, not new behavior)

This stage is explicitly **not** part of the structured-JSON pipeline plan — `app/ai/site_generator.py` is unchanged and still reads `blueprint/design.md`. This only confirms the existing generator still works against the new pipeline's output.

**`POST /api/v1/debug/design-md/{project_id}`** — regenerates `blueprint/design.md` from `blueprint.json` (or `scraped.json` if you haven't run Stage 2 yet). No body.

Then generate as today: **`POST /api/v1/projects/{id}/generate?tier=pro`** (existing debug route — this one still requires a `Project` DB row to exist, since generation writes `Project.status`/`GenerationJob`/`GenerationOutput` rows; it isn't DB-free like the three routes above).

**Check:** the site still builds successfully end-to-end, uses the real reviewed copy and images, and nothing regressed compared to a pre-pipeline `design.md`-based run.

---

## Alternative: scripting instead of the API

If you'd rather script it (e.g. to batch-test several URLs), each stage is also a plain importable function — run these from `backend/` with `./venv/Scripts/python.exe`:

```python
# Stage 1
from pathlib import Path
import json
from app.ai.blueprint_extraction import extract_scraped_json

project_root = Path("storage_data/projects/<PROJECT_ID>")  # any folder is fine, doesn't need to pre-exist
scraped = extract_scraped_json(project_root)               # requires metadata.json + snapshot/ already there (i.e. already crawled)
```

```python
# Stage 2 (reads scraped.json written by Stage 1)
from app.ai.blueprint_schema import BlueprintDocument
from app.ai.blueprint_review import review_blueprint

scraped = BlueprintDocument.model_validate(json.loads((project_root / "blueprint" / "scraped.json").read_text()))
blueprint, usage = review_blueprint(project_root, scraped)
```

```python
# Stage 3 prep (reads blueprint.json written by Stage 2)
from app.ai.blueprint_legacy_compat import render_design_md_compat

blueprint = BlueprintDocument.model_validate(json.loads((project_root / "blueprint" / "blueprint.json").read_text()))
design_md = render_design_md_compat(blueprint)
```

The API route wraps exactly this code plus the crawl step and file writes — use whichever is more convenient.

## Note on Stage 3's actual future

Per the approved plan, generation itself (scoping to a single home-page one-shot build directly off `blueprint.json`, dropping the `design.md` intermediate entirely) is separate follow-up work, not covered here or in `blueprint-json-pipeline-plan.md`. Stage 3 above exists only to prove the current pipeline doesn't break what already works.
