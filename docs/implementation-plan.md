# ReDoWebs — Implementation Plan

## Context

ReDoWebs is a brand-new, greenfield build — the working directory currently contains only `rule.md` (mandating a `frontend/` / `backend/` / `docs/` / `standalone/` repo layout). There is no existing code to reconcile with.

The product: a logged-in user submits the URL of an existing small static website (≤3 pages, no server-rendered backend). The system crawls it (respecting `robots.txt`), extracts a structured blueprint (content, nav, branding assets, colors, fonts, metadata, layout) into a semi-structured `design.md`, and uses AI (via OpenRouter) to generate tiered redesigns from that single blueprint using randomly-selected, DB-stored prompt-strategy variants per tier. Tiers (originally conceived as a fixed Basic/Premium/Pro) are now a **dynamic, admin-manageable list** — each tier row can be independently enabled/disabled, renamed, reordered, and priced; disabled tiers are skipped entirely during generation. **Current build/test phase runs only the `pro` tier** while its prompt templates and generation mechanism are being validated; `basic`/`premium` exist as disabled placeholders. Users preview all enabled tiers unlimited times and can hand-edit `design.md` to regenerate (each regeneration/generation costs 1 credit from a unified wallet). Downloading the generated source folder costs additional, admin-configurable credits per tier (stored on the tier row itself). Credits are purchased in admin-configurable packs via one-time PayPal payments (account or card); new signups get 3 free credits (enough to preview, never enough alone to download, which is intentional — downloads always require payment).

This plan was reached through an extensive interview covering product scope, credit economics, auth, crawler limits, legal/ownership risk mitigation (ToS checkbox + logging, no domain verification), job retry behavior, testing bar, observability, and blueprint structure — all decisions below reflect explicit user choices, not assumptions, except where marked as an implementation-detail judgment call consistent with those choices.

See [PRD.md](PRD.md) for the product-level framing (problem, users, scope, requirements, success metrics) this plan implements.

## Tech Stack (confirmed)

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 + Alembic, Postgres-backed job queue for background jobs (originally planned as Celery + Redis; switched 2026-09-06 since Redis had no other use in the app — see the "Job Orchestration" section below), SQLAdmin (admin panel), OpenRouter (LLM access, GPT-4o-mini for dev/test phase)
- **Frontend**: Angular (standalone components, functional route guards)
- **DB**: PostgreSQL
- **Payments**: PayPal (Orders v2 + JS SDK buttons, PayPal account or card, one-time credit packs, no subscriptions) — switched from Stripe 2026-10-05, see `docs/paypal-payments-plan.md`
- **Storage**: local disk in v1, behind a thin `StorageBackend` abstraction so S3 can be swapped in later without touching callers
- **Deployment**: Docker Compose (`standalone/`), production target AWS (not locked in, nothing AWS-specific built now)

## Repo / Module Structure

```
ReDoWebs/
├── rule.md
├── docs/                     # PRD.md, implementation-plan.md, architecture.md, db-schema.md, api-spec.md, adr/
├── frontend/                 # Angular app
│   └── src/app/
│       ├── core/             # auth/, api/, errors/ (interceptors, guards, base http wrappers)
│       ├── shared/           # presentational components, pipes
│       └── features/
│           ├── landing/, auth/, dashboard/, project-submit/,
│           ├── project-detail/ (job polling + 3-tier preview compare)
│           ├── design-editor/ (raw design.md textarea + regenerate)
│           ├── checkout/, account/
├── backend/
│   ├── alembic/
│   └── app/
│       ├── main.py           # app factory, router + SQLAdmin mounting
│       ├── config.py         # pydantic Settings
│       ├── db/                # session.py, base.py
│       ├── models/            # user.py, wallet.py, project.py, blueprint.py, template.py, job.py, billing.py, config.py, token_usage.py
│       ├── schemas/           # Pydantic DTOs mirroring models/
│       ├── routers/           # thin HTTP layer only: auth.py, projects.py, jobs.py, blueprints.py, credits.py, billing.py, downloads.py
│       ├── services/          # all business logic: auth_service.py, wallet_service.py, project_service.py, template_service.py, billing_service.py, download_service.py, admin_config_service.py
│       ├── crawler/            # discover.py, robots.py, fetch.py, errors.py
│       ├── ai/                 # openrouter_client.py, blueprint_extractor.py, prompt_templates.py, site_generator.py
│       ├── storage/             # base.py (StorageBackend protocol), local_disk.py
│       ├── workers/              # queue.py, queue_worker.py, tasks_crawl.py, tasks_blueprint.py, tasks_generate.py (Postgres-backed queue, not Celery -- see "Job Orchestration")
│       ├── admin/                # sqladmin_views.py
│       ├── core/                # security.py (JWT/hashing), rate_limit.py, logging.py (structlog)
│       └── deps.py
│   └── tests/unit/            # test_wallet_service.py, test_pricing.py, test_billing_service.py, test_auth_permissions.py, test_template_selection.py
└── standalone/
    ├── docker-compose.yml
    └── .env.example
```

Routers stay thin (parse → call service → return schema) so queue-worker task handlers and SQLAdmin custom actions can reuse the same service functions instead of duplicating logic behind HTTP.

## Database Schema (Postgres, UUID PKs)

- **users**: email, password_hash (nullable, unused until password auth ships), is_email_verified, is_active, is_admin
- **auth_identities**: user_id FK, provider enum(`password`,`google`,`apple`), provider_user_id, unique(provider, provider_user_id) — models identity as a separate linkable table (not columns on `users`) specifically so Apple SSO can be added later as a new enum value + new router, zero migration on `users`
- **email_verification_tokens** / **password_reset_tokens**: hashed tokens, expiry, used_at — still pending; only Google SSO is implemented so far, no password-based signup path exists yet
- ~~**refresh_tokens**~~ (removed 2026-08-03, dropped via `7f3a1c9e4b21_drop_refresh_tokens.py`): existed briefly for a server-side-revocable refresh session; replaced by a single longer-lived JWT with no refresh/rotation, matching the reference architecture the user asked to mirror exactly (see Auth section below).
- **credit_wallets**: user_id FK unique, balance (denormalized cache, never the source of truth for spend decisions)
- **credit_transactions** (ledger, ground truth): wallet_id, amount (signed), reason enum(`signup_grant`,`purchase`,`generation_spend`,`regeneration_spend`,`download_spend`,`admin_adjustment`,`system_reversal`), related_project_id/job_id/purchase_id, idempotency_key unique nullable
- **projects**: user_id (NOT NULL as of the Google SSO milestone — every submission now requires a logged-in user; see Auth section), source_url, status enum(`pending`,`crawling`,`blueprint_ready`,`generating`,`ready`,`failed`,`rejected`), rejection_reason, tos_accepted, submitted_ip
- **submission_logs** (append-only, abuse/DMCA record): user_id, url, ip, user_agent, tos_accepted, created_at
- **crawl_snapshots** / **crawl_pages** / **assets**: crawl results, per-page status, downloaded asset metadata (asset_type incl. logo/font/icon)
- **blueprints**: project_id, version (monotonic per project), source enum(`ai_extracted`,`user_edited`), design_md_storage_path, denormalized frontmatter fields (site_name, colors, logo_path, fonts) for quick querying, is_current flag — versions are immutable, never overwritten
- **tiers** (changed from a fixed enum to a dynamic, admin-manageable table): id, key (slug, e.g. `basic`/`premium`/`pro`), label, is_active (admin on/off toggle — disabled tiers are skipped entirely during generation, not just hidden), sort_order, download_credit_cost — admin can add, rename, reorder, price, and enable/disable tiers here without a code change. Replaces the old `admin_config.download_cost_basic/premium/pro` keys, which are removed now that cost lives on the tier row itself. **Current test phase: only the `pro` tier row is active** — `basic`/`premium` exist but are disabled until their own prompt templates are ready.
- **design_strategy_templates**: tier_id FK → tiers, prompt_text, is_active, weight — admin-managed via SQLAdmin. Weighted-random selection only ever considers `is_active=true` templates whose parent tier is also `is_active=true`.
- **generation_jobs**: project_id, blueprint_id, stage enum (drives progress UI; stage values are generated dynamically per enabled tier rather than hardcoded to 3), overall_status, failure_reason, credit_transaction_id
- **generation_outputs** (one row per enabled tier per job): job_id, tier_id FK, template_id FK (records which template was used), output_storage_path, preview_url_path
- **purchases**: user_id, credit_pack_id, paypal_order_id unique, paypal_capture_id unique, credits_granted + amount_usd_cents (snapshot at order time), status (pending/completed/failed/refunded), source (paypal/manual_admin) — webhook idempotency comes from the row lock + the `purchase:{id}` ledger key, not a stored event id
- **credit_packs**: name, credits, price_usd_cents, is_active, sort_order — admin-editable, disabled not deleted
- **admin_config**: key/value (typed columns), seeded with `usd_per_credit=<default>` — per-tier download cost moved to `tiers.download_credit_cost` (see above); this table now only holds cost/pricing config that isn't tier-specific
- **token_usage_logs** (implemented 2026-08-03): project_id, user_id, job_id (nullable), model_name, purpose (`blueprint_extraction`|`generation`), prompt_tokens, completion_tokens, cost_estimate_usd — internal-only, never user-facing. **Deviates from this table's original job_id-first design**: keyed by `project_id` (always available) rather than `job_id` alone, because blueprint extraction's vision-model call happens before any `generation_jobs` row exists — `job_id` is populated only for `purpose="generation"` rows. Written from both `tasks_blueprint.py` and `tasks_generate.py` (`token_usage_service.record_usage()`), closing a gap where the blueprint-extraction vision call's usage was previously discarded entirely.

**Race-condition-safe credit spend** (the one place this logic lives — `wallet_service.spend()`): `SELECT balance FROM credit_wallets WHERE user_id = :uid FOR UPDATE` inside a transaction, check balance, insert ledger row, update balance, commit. The row-level lock serializes concurrent spend attempts so two simultaneous download requests against an insufficient balance can't both succeed. Every credit-consuming path (generation, regeneration, download) calls this one function — no ad hoc balance checks elsewhere.

**Credit-charge timing for "no charge on failure"**: `POST /projects` does a fast synchronous pre-check (robots.txt + homepage fetch + nav-link discovery/page-count) and returns a rejection immediately with zero credit spend if it fails. Only after this passes does the endpoint debit 1 credit and enqueue the full crawl→blueprint→generate pipeline (a Postgres-backed queue chain, not Celery — see "Job Orchestration"). If the full crawl still hard-fails despite the pre-check (rare), the failure handler issues an automatic refund transaction (`reason=system_reversal`) — a safety net, not the primary mechanism.

## API Surface (`/api/v1`, JWT bearer except where noted)

- **Auth** (Google SSO only — password register/login/verify-email/reset still pending): `GET /auth/google/authorize` (rate-limited via `rate_limit_auth`, redirects to Google, sets a short-lived `oauth_state` CSRF cookie), `GET /auth/google/callback` (Google's redirect target — exchanges the code, issues a JWT, redirects to the frontend's `/auth/callback?token=`), `GET /auth/me`. No `/auth/refresh` or `/auth/logout` routes — see Auth section below for why.
- **Projects**: `POST /projects` (url + tos_accepted, requires auth, rate-limited via `rate_limit_submit`), `GET /projects` (implemented — lists the current user's own projects, newest first; doubles as the per-user generation history view), `GET /projects/{id}` (requires auth; 404s — not 403s, to avoid leaking existence — if the project isn't the caller's)
- **Jobs**: `GET /jobs/{id}` (stage/status for polling), `GET /projects/{id}/jobs`
- **Blueprints**: version list, `GET /blueprints/{id}`, `PUT /blueprints/{id}` (free draft save, validates required frontmatter), `POST /projects/{id}/regenerate` (credit-spending, creates new version, enqueues generation-only chain)
- **Credits**: `GET /credits/wallet`, `GET /credits/transactions`
- **Billing**: `GET /billing/config`, `GET /billing/credit-packs` (both public), `POST /billing/paypal/orders`, `POST /billing/paypal/orders/{id}/capture`, `GET /billing/purchases`, `POST /billing/paypal/webhook` (PayPal-signature-verified, no JWT); public `GET /tiers` for download costs
- **Downloads**: `POST /projects/{id}/download` (tier-cost credit spend via wallet_service, assembles/serves folder)
- **Admin**: mounted separately via SQLAdmin at `/admin`, gated by `is_admin`, reusing the same auth session (not a parallel login system)

## Job Orchestration (originally planned as Celery, since 2026-09-06 a Postgres-backed queue)

**Superseded (2026-09-06) — see CLAUDE.md and docs/PROGRESS.md for what's actually built**: Celery+Redis was removed since Redis had no other use in the app (rate limiting is in-memory slowapi, auth is JWT). The pipeline now runs on a `queued_jobs` Postgres table polled by `app/workers/queue_worker.py` (`SELECT ... FOR UPDATE SKIP LOCKED` to claim a row), with each stage enqueueing the next on its own success path instead of a Celery `chain()`/`group()`. **No auto-retry was ever actually implemented** (a deliberate decision, unlike the retry policy originally planned below) — any exception, transient or definitive, immediately marks the project `failed`/`rejected`.

**Original plan (kept for context on what changed)**: `crawl_site` → `extract_blueprint` → `group(generate_tier(t) for t in get_enabled_tiers())` → `finalize_job`, as Celery tasks. The group would be built dynamically from whichever tiers are currently active (today, just `pro`) rather than a hardcoded 3-way group — this part is still true today, just implemented as sequential `remaining_tiers` chaining rather than a parallel `group`, since only one tier is enabled so far. Regeneration path starts at the tier-generation step directly (edited `design.md` IS the new blueprint, no re-crawl) — not yet built (Milestone 3/5).

Originally planned retry policy (not implemented): transient errors (timeouts, 429/5xx) auto-retry 2-3x with exponential backoff; definitive errors (`SiteInaccessible`, `CrawlRejected` for >3 pages, robots.txt disallow, login-wall heuristics) fail immediately, no retry, no credit charged (or refunded per the system_reversal path above).

## Crawler

No headless browser in v1 — plain `httpx` fetch + BeautifulSoup/selectolax parse is sufficient for the target audience (static, no-backend, ≤3-page sites); flagged as a known limitation if a submitted "static" site turns out to be a disguised JS-rendered SPA. Page discovery follows same-origin nav/homepage links breadth-first; discovering a 4th distinct page raises `CrawlRejected` with a clear message — **the whole submission is rejected, not silently truncated to 3 pages**. `robots.txt` fetched first via `urllib.robotparser`/`protego`; homepage disallow is a hard reject. Assets (`img`, icons, `@font-face`, stylesheet-referenced backgrounds) are downloaded once per unique URL into `projects/{id}/snapshot/{asset_type}/...` and recorded in `assets`.

## Blueprint Extraction & Generation Pipeline

Extraction aggregates crawled content/nav/headings into markdown prose, then fires two independent OpenRouter review calls concurrently (via a small `ThreadPoolExecutor`, since the task handler is synchronous) from `blueprint_extractor.py`: a **brand review** call (vision-capable, only runs if a logo image was found) that confirms site name, fonts, and tone — filling the required YAML frontmatter of `design.md` — and a **content-gap review** call (text-only, always runs) that checks a compact digest of the scraped content against four standard sections (About/Value Proposition, Services/Features summary, Call To Action, FAQ) and drafts a short, tone-matched replacement for any that are genuinely missing, using only facts already present in the scraped content. Drafted sections are appended to the homepage's markdown body, each marked with an `<!-- ai-drafted -->` comment for traceability. The content-gap prompt carries an absolute rule never to draft or imply testimonials, statistics/numeric claims, pricing, credentials/awards, or contact details — those are left out entirely if the source site doesn't have them, never fabricated. Splitting into two calls (rather than one combined call) is a deliberate robustness/accuracy choice: a JSON-parse failure or off-format response in the creative content-gap half no longer takes down the well-established brand-fields half, and each prompt stays narrowly scoped to one job. The two calls' token usage is summed into a single `blueprint_extraction` row in `token_usage_logs`. If the content-gap call fails, extraction degrades gracefully (no sections added) rather than failing the project; a brand-review failure still fails the task, unchanged from before.

**Token usage is now recorded for every AI call (implemented 2026-08-03)**: both `tasks_blueprint.py` (vision call, `purpose="blueprint_extraction"`) and `tasks_generate.py` (agentic loop, `purpose="generation"`) call `token_usage_service.record_usage()` to write a `token_usage_logs` row (see Database Schema) tied to `user_id` and `model_name`. Previously the blueprint-extraction vision call's usage was silently discarded (`_usage` variable, unused) — only the generation step's `prompt_tokens`/`completion_tokens` were captured, on `generation_outputs`, with no link to a user or model name.

**Generation is an agentic tool-calling loop, not a single-shot completion** (revised from the original plan below, per explicit user decision): `site_generator.py` picks a random design-strategy template from `backend/prompts/*.txt` for the tier (currently only `pro` is enabled), and runs a manual OpenAI-style tool-calling loop against **OpenRouter** (model: `anthropic/claude-sonnet-4.5` by default, configurable) — the design-strategy `.txt` file content is used directly as the system prompt (these files are themselves written as agent instructions: "identify the tech stack, build a mental model, ask focused questions..." — an addendum in code overrides the tech-stack-discovery instinct since there's no existing codebase, and constrains output to plain HTML/CSS/JS with Tailwind or Bootstrap via CDN, no build tooling). The model is given three tools — `write_file`, `read_file`, `list_files` — sandboxed (path-traversal-checked) to the project's `generated/{tier}/` output folder, which is pre-populated with the real downloaded images before the loop starts. The loop runs until the model responds with no further tool calls (its final message is the human-readable summary), bounded by `generation_max_iterations`. **Why OpenRouter instead of Anthropic's native Tool Runner**: the user only has an OpenRouter key; OpenRouter speaks an OpenAI-compatible wire format, not Anthropic's native Messages API, so Anthropic SDK features (Tool Runner, `@beta_tool`) can't point at it — the loop is hand-rolled (`_run_agent_loop` in `site_generator.py`) instead.

**Original plan (superseded, kept for context on what changed)**: a single JSON-mode completion producing `{pages, css, js}`, with deterministic post-processing in code for alt text/meta tags/contrast/sitemap. That post-processing (meta/OG tags, alt text, WCAG contrast check, `sitemap.xml` generation) is **not yet implemented** against the new agentic-output path and is a known gap — see `docs/PROGRESS.md`. Each `generation_outputs` row (once DB-wired) should record which `template_id` was used, same as originally planned. Once `basic`/`premium` are enabled later, their prompts should be written so each enabled tier is visibly more polished than the one below it — that ordering rubric is only meaningful once more than one tier is active, so it's deferred rather than enforced today.

## Admin Panel (SQLAdmin)

Auto-registered CRUD for all models; `DesignStrategyTemplate` and `AdminConfig` are the ones admins actively edit. Two things need custom SQLAdmin actions rather than raw generic forms: **manual credit refund** (a button calling `wallet_service.admin_adjust(...)` server-side, not a free-form ledger insert, to keep `credit_wallets.balance` consistent) and **PayPal reconciliation on refunded payments** (same mechanism — refunds are marked on the purchase by the webhook, never reversed automatically). SQLAdmin auth reuses the app's existing session/JWT via a custom `AuthenticationBackend` gated on `User.is_admin` — no second login system.

## Auth

Email/password with argon2 hashing, email verification required before first submission/purchase (not before login), self-service password reset (hashed tokens, short TTL) — **still pending**, not yet built. `AuthIdentity` model is what makes Apple SSO a fast-follow (new enum value + new router) instead of a schema rework.

**Google SSO (implemented 2026-08-03, switched to server-side redirect flow 2026-08-03)**: originally used the Google Identity Services ID-token flow; **replaced at the user's explicit request** to mirror a reference project's architecture (`G:\Web modernizer\doc\ARCHITECTURE.md`) exactly. Now uses the standard **server-side authorization-code redirect flow**: `GET /api/v1/auth/google/authorize` builds Google's consent-screen URL (`client_id`, `redirect_uri=REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI`, `scope=openid email profile`, a fresh `state`), sets `state` in a short-lived httpOnly `oauth_state` cookie, and redirects the browser. Google redirects back to `GET /api/v1/auth/google/callback`, which verifies `state` against the cookie, exchanges the `code` for tokens via a direct POST to Google's token endpoint (`httpx`, no new dependency), verifies the returned `id_token` the same way as before (`google.oauth2.id_token.verify_oauth2_token`, audience = `REDOWEBS_GOOGLE_CLIENT_ID`), then calls `auth_service.authenticate_google(claims, db)` — same find-by-identity → link-by-verified-email → create-new-user logic as before, now taking already-verified claims instead of a raw ID token (the router owns the transport/verification step; the service owns the account logic). On success it redirects to `{REDOWEBS_FRONTEND_URL}/auth/callback?token=<jwt>`; the Angular `AuthCallbackComponent` (no guard, mirrors the reference's route) reads the token, calls `/auth/me`, and stores both in `sessionStorage`. The frontend no longer talks to Google directly — no GIS JS SDK, no Client ID on the frontend, no `GoogleSignInButtonComponent`. Requires `REDOWEBS_GOOGLE_CLIENT_SECRET` (new, server-side flow needs it) and the exact `REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI` registered as an authorized redirect URI in the Google Cloud Console OAuth client.

**Token/session model (changed 2026-08-03, matching the same reference project)**: dropped the access+refresh-token pair entirely. A single JWT (`REDOWEBS_JWT_EXPIRE_DAYS`, default 7 days) is issued on login and stored in the frontend's `sessionStorage` (not memory) — restored synchronously on page load, no bootstrap network call needed. The `refresh_tokens` table, `POST /auth/refresh`, and `POST /auth/logout` are all removed (migration `7f3a1c9e4b21_drop_refresh_tokens.py`) — there's no server-side session left to rotate or revoke, so logout is purely client-side (`AuthService.logout()` clears `sessionStorage`, no backend call). **Known trade-off, accepted explicitly by the user**: this loses forced-logout/server-side revocation compared to the previous refresh-token design — a leaked JWT stays valid until it expires. `authErrorInterceptor` (new) forces a client-side logout on any `401` except calls to `/auth/*` itself.

**Ownership + rate limiting (unaffected by the redirect-flow switch)**: `projects.user_id` is still NOT NULL — `POST /api/v1/projects` requires a valid access token (`get_current_user` FastAPI dependency, unchanged) and `GET /api/v1/projects/{id}` 404s (not 403s, to avoid leaking existence of other users' projects) if the project isn't the caller's. `GET /auth/google/authorize` and `POST /projects` are IP-rate-limited via `slowapi` (`app/rate_limit.py`'s shared `Limiter`, keyed by `get_remote_address`), configured via `rate_limit_auth`/`rate_limit_submit` in `config.py`.

## Frontend Routes

`/`, `/auth/*` (signup, login, verify-email, forgot/reset password), `/dashboard`, `/projects/new`, `/projects/:id` (job-status stepper → iframe preview comparison across whatever tiers are currently enabled, with per-tier download button), `/projects/:id/edit` (design.md textarea, Save Draft vs Regenerate-costs-1-credit), `/billing/checkout`, `/account` (wallet balance, transaction history, linked identities). Job polling via a shared RxJS `timer`-based service (3s interval, auto-stops on terminal status) — no WebSockets.

## Testing (per confirmed bar: core logic unit-tested, rest manual)

Unit tests: `wallet_service` (spend success/failure, **concurrent-spend race test**, admin_adjust), `admin_config_service` pricing getters reflect DB changes, PayPal capture/webhook (signature verification, exactly-once crediting under capture/webhook races, amount-mismatch rejection), auth/permission gates (unverified-user blocks, admin-only gates, JWT/refresh revocation), weighted template selection (respects `is_active`, weight ratios — assert via mocked `random.choices` args, not statistical sampling). Crawler accuracy and AI output/tier-differentiation quality are verified manually — no automated e2e for subjective AI output.

## Observability & Rate Limiting

Structured JSON logging (structlog/loguru) across backend + the queue worker; Sentry for exception capture and failed-job alerting. `slowapi` rate limits (in-memory today, not Redis-backed — see "Job Orchestration") on: crawl submission (`POST /projects`), login, register, password-reset request.

## Docker Compose (`standalone/`)

Services: `postgres`, `backend` (uvicorn, runs `alembic upgrade head` on startup), `queue-worker` (`python -m app.workers.queue_worker`, no Redis/broker container needed — see "Job Orchestration"), `frontend` (Angular dev server), `mailhog` (dev SMTP catcher for verification/reset emails). A shared `storage_data` volume mounts into both `backend` and `queue-worker` at the same path — the one place local-disk storage needs care, since the API serves downloads while the worker writes generated output.

## Build Order / Milestones

1. **Scaffolding** — repo skeleton, Compose stack boots empty, Alembic wired.
2. **Core loop (highest risk, build first)** — stub auth, crawler → blueprint → 3-tier generation working end-to-end with a bare Angular submit/poll/preview flow. No credits, no admin, no Stripe. This proves the product concept.
3. **design.md editing & regeneration** — free (no credit gate yet) to validate versioning mechanics.
4. **Credit/wallet system** — `wallet_service` with row-locking spend (TDD, tests first), signup grant, wire generation/regeneration to spend real credits, wire the pre-check/no-charge-on-reject path.
5. **Downloads + AdminConfig** — tier-cost spend, folder assembly, download endpoint/UI.
6. **Auth hardening** — real email verification, password reset, Google OAuth, JWT+refresh sessions.
7. **PayPal billing** — admin-configurable credit packs, order create/capture, webhook + idempotency (tests alongside), credit-pack purchase UI.
8. **Admin panel** — SQLAdmin mount, all ModelViews, custom refund action.
9. **Observability & rate limiting** — structlog, Sentry, slowapi on the flagged endpoints, confirm submission_logs works end to end.
10. **Polish** — SEO/accessibility verification pass, tier-differentiation prompt tuning, UI polish, any deferred tests.

This order front-loads the one genuinely uncertain piece — does crawl→blueprint→AI-generation actually produce good, differentiated output — before investing in payments/auth/admin plumbing that's comparatively well-understood engineering.

## Verification

- Milestone 2 end-to-end check: submit a real small static site's URL, confirm job progresses through all stages, confirm `design.md` has valid frontmatter + sensible prose, confirm all 3 tier previews render and are visibly different in polish (Pro > Premium > Basic).
- Milestone 4: run `pytest backend/tests/unit/test_wallet_service.py` including the concurrent-spend test; manually attempt two rapid download clicks against a low balance to confirm only one succeeds.
- Milestone 7: buy a pack in the PayPal sandbox (account and card), re-POST the capture and confirm no double credit; for webhooks, register the sandbox webhook against a public URL (ngrok or Railway) and use PayPal's webhook simulator.
- Milestone 8: confirm a non-admin JWT is rejected at `/admin`, confirm the custom refund action updates both the ledger and `credit_wallets.balance` consistently.
- Full run: `docker compose -f standalone/docker-compose.yml up`, exercise the complete user journey (signup → verify → submit → preview → regenerate → buy credits → download) manually before calling v1 done.
