# ReDoWebs — Implementation Plan

## Context

ReDoWebs is a brand-new, greenfield build — the working directory currently contains only `rule.md` (mandating a `frontend/` / `backend/` / `docs/` / `standalone/` repo layout). There is no existing code to reconcile with.

The product: a logged-in user submits the URL of an existing small static website (≤3 pages, no server-rendered backend). The system crawls it (respecting `robots.txt`), extracts a structured blueprint (content, nav, branding assets, colors, fonts, metadata, layout) into a semi-structured `design.md`, and uses AI (via OpenRouter) to generate tiered redesigns from that single blueprint using randomly-selected, DB-stored prompt-strategy variants per tier. Tiers (originally conceived as a fixed Basic/Premium/Pro) are now a **dynamic, admin-manageable list** — each tier row can be independently enabled/disabled, renamed, reordered, and priced; disabled tiers are skipped entirely during generation. **Current build/test phase runs only the `pro` tier** while its prompt templates and generation mechanism are being validated; `basic`/`premium` exist as disabled placeholders. Users preview all enabled tiers unlimited times and can hand-edit `design.md` to regenerate (each regeneration/generation costs 1 credit from a unified wallet). Downloading the generated source folder costs additional, admin-configurable credits per tier (stored on the tier row itself). Credits are purchased in packs via one-time Stripe payments; new signups get 3 free credits (enough to preview, never enough alone to download, which is intentional — downloads always require payment).

This plan was reached through an extensive interview covering product scope, credit economics, auth, crawler limits, legal/ownership risk mitigation (ToS checkbox + logging, no domain verification), job retry behavior, testing bar, observability, and blueprint structure — all decisions below reflect explicit user choices, not assumptions, except where marked as an implementation-detail judgment call consistent with those choices.

See [PRD.md](PRD.md) for the product-level framing (problem, users, scope, requirements, success metrics) this plan implements.

## Tech Stack (confirmed)

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 + Alembic, Celery + Redis (background jobs), SQLAdmin (admin panel), OpenRouter (LLM access, GPT-4o-mini for dev/test phase)
- **Frontend**: Angular (standalone components, functional route guards)
- **DB**: PostgreSQL
- **Payments**: Stripe (one-time checkout, no subscriptions)
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
│       ├── workers/              # celery_app.py, tasks_crawl.py, tasks_blueprint.py, tasks_generate.py
│       ├── admin/                # sqladmin_views.py
│       ├── core/                # security.py (JWT/hashing), rate_limit.py, logging.py (structlog)
│       └── deps.py
│   └── tests/unit/            # test_wallet_service.py, test_pricing.py, test_stripe_webhook.py, test_auth_permissions.py, test_template_selection.py
└── standalone/
    ├── docker-compose.yml
    └── .env.example
```

Routers stay thin (parse → call service → return schema) so Celery tasks and SQLAdmin custom actions can reuse the same service functions instead of duplicating logic behind HTTP.

## Database Schema (Postgres, UUID PKs)

- **users**: email, password_hash (nullable, unused until password auth ships), is_email_verified, is_active, is_admin
- **auth_identities**: user_id FK, provider enum(`password`,`google`,`apple`), provider_user_id, unique(provider, provider_user_id) — models identity as a separate linkable table (not columns on `users`) specifically so Apple SSO can be added later as a new enum value + new router, zero migration on `users`
- **refresh_tokens** (implemented 2026-08-03, alongside Google SSO): user_id FK, token_hash (SHA-256 of the raw token — the raw value is never persisted), expires_at, revoked_at (nullable) — this table is what makes the refresh token *server-side revocable*: `auth_service.refresh_access_token()` rotates it on every use (old row revoked, new row issued) and `auth_service.logout()` revokes it directly. A stateless JWT refresh token couldn't support either.
- **email_verification_tokens** / **password_reset_tokens**: hashed tokens, expiry, used_at — still pending; only Google SSO is implemented so far, no password-based signup path exists yet
- **credit_wallets**: user_id FK unique, balance (denormalized cache, never the source of truth for spend decisions)
- **credit_transactions** (ledger, ground truth): wallet_id, amount (signed), reason enum(`signup_grant`,`purchase`,`generation_spend`,`regeneration_spend`,`download_spend`,`admin_adjustment`,`system_reversal`), related_project_id/job_id/purchase_id, idempotency_key unique nullable
- **projects**: user_id (NOT NULL as of the Google SSO milestone — every submission now requires a logged-in user; see Auth section), source_url, status enum(`pending`,`crawling`,`blueprint_ready`,`generating`,`ready`,`failed`,`rejected`), rejection_reason, tos_accepted, submitted_ip
- **submission_logs** (append-only, abuse/DMCA record): user_id, url, ip, user_agent, tos_accepted, created_at
- **crawl_snapshots** / **crawl_pages** / **assets**: crawl results, per-page status, downloaded asset metadata (asset_type incl. logo/font/icon)
- **blueprints**: project_id, version (monotonic per project), source enum(`ai_extracted`,`user_edited`), design_md_storage_path, denormalized frontmatter fields (site_name, colors, logo_path, fonts) for quick querying, is_current flag — versions are immutable, never overwritten
- **tiers** (changed from a fixed enum to a dynamic, admin-manageable table): id, key (slug, e.g. `basic`/`premium`/`pro`), label, is_active (admin on/off toggle — disabled tiers are skipped entirely during generation, not just hidden), sort_order, download_credit_cost — admin can add, rename, reorder, price, and enable/disable tiers here without a code change. Replaces the old `admin_config.download_cost_basic/premium/pro` keys, which are removed now that cost lives on the tier row itself. **Current test phase: only the `pro` tier row is active** — `basic`/`premium` exist but are disabled until their own prompt templates are ready.
- **design_strategy_templates**: tier_id FK → tiers, prompt_text, is_active, weight — admin-managed via SQLAdmin. Weighted-random selection only ever considers `is_active=true` templates whose parent tier is also `is_active=true`.
- **generation_jobs**: project_id, blueprint_id, celery_task_id, stage enum (drives progress UI; stage values are generated dynamically per enabled tier rather than hardcoded to 3), overall_status, failure_reason, credit_transaction_id
- **generation_outputs** (one row per enabled tier per job): job_id, tier_id FK, template_id FK (records which template was used), output_storage_path, preview_url_path
- **purchases**: user_id, stripe_checkout_session_id unique, stripe_event_id unique (webhook idempotency), credit_pack_credits, amount_usd_cents, status
- **admin_config**: key/value (typed columns), seeded with `usd_per_credit=<default>` — per-tier download cost moved to `tiers.download_credit_cost` (see above); this table now only holds cost/pricing config that isn't tier-specific
- **token_usage_logs** (implemented 2026-08-03): project_id, user_id, job_id (nullable), model_name, purpose (`blueprint_extraction`|`generation`), prompt_tokens, completion_tokens, cost_estimate_usd — internal-only, never user-facing. **Deviates from this table's original job_id-first design**: keyed by `project_id` (always available) rather than `job_id` alone, because blueprint extraction's vision-model call happens before any `generation_jobs` row exists — `job_id` is populated only for `purpose="generation"` rows. Written from both `tasks_blueprint.py` and `tasks_generate.py` (`token_usage_service.record_usage()`), closing a gap where the blueprint-extraction vision call's usage was previously discarded entirely.

**Race-condition-safe credit spend** (the one place this logic lives — `wallet_service.spend()`): `SELECT balance FROM credit_wallets WHERE user_id = :uid FOR UPDATE` inside a transaction, check balance, insert ledger row, update balance, commit. The row-level lock serializes concurrent spend attempts so two simultaneous download requests against an insufficient balance can't both succeed. Every credit-consuming path (generation, regeneration, download) calls this one function — no ad hoc balance checks elsewhere.

**Credit-charge timing for "no charge on failure"**: `POST /projects` does a fast synchronous pre-check (robots.txt + homepage fetch + nav-link discovery/page-count) and returns a rejection immediately with zero credit spend if it fails. Only after this passes does the endpoint debit 1 credit and enqueue the full crawl→blueprint→generate Celery chain. If the full crawl still hard-fails despite the pre-check (rare), the failure handler issues an automatic refund transaction (`reason=system_reversal`) — a safety net, not the primary mechanism.

## API Surface (`/api/v1`, JWT bearer except where noted)

- **Auth** (implemented 2026-08-03, Google SSO only — password register/login/verify-email/reset still pending): `POST /auth/google` (body `{id_token}`, rate-limited via `rate_limit_auth`), `POST /auth/refresh` (reads the refresh cookie, rotates it), `POST /auth/logout` (revokes the refresh cookie), `GET /auth/me`
- **Projects**: `POST /projects` (url + tos_accepted, requires auth, rate-limited via `rate_limit_submit`), `GET /projects` (implemented — lists the current user's own projects, newest first; doubles as the per-user generation history view), `GET /projects/{id}` (requires auth; 404s — not 403s, to avoid leaking existence — if the project isn't the caller's)
- **Jobs**: `GET /jobs/{id}` (stage/status for polling), `GET /projects/{id}/jobs`
- **Blueprints**: version list, `GET /blueprints/{id}`, `PUT /blueprints/{id}` (free draft save, validates required frontmatter), `POST /projects/{id}/regenerate` (credit-spending, creates new version, enqueues generation-only chain)
- **Credits**: `GET /credits/wallet`, `GET /credits/transactions`
- **Billing**: `GET /billing/credit-packs`, `POST /billing/checkout-session`, `POST /billing/webhook` (Stripe-signature-verified, no JWT)
- **Downloads**: `POST /projects/{id}/download` (tier-cost credit spend via wallet_service, assembles/serves folder)
- **Admin**: mounted separately via SQLAdmin at `/admin`, gated by `is_admin`, reusing the same auth session (not a parallel login system)

## Celery Task Chain

`crawl_site` → `extract_blueprint` → `group(generate_tier(t) for t in get_enabled_tiers())` → `finalize_job`. The group is built dynamically from whichever tiers are currently active (today, just `pro`) rather than a hardcoded 3-way group. Regeneration path starts at the `group(...)` step directly (edited `design.md` IS the new blueprint, no re-crawl).

Retry policy: transient errors (timeouts, 429/5xx) auto-retry 2-3x with exponential backoff; definitive errors (`SiteInaccessible`, `CrawlRejected` for >3 pages, robots.txt disallow, login-wall heuristics) fail immediately, no retry, no credit charged (or refunded per the system_reversal path above).

## Crawler

No headless browser in v1 — plain `httpx` fetch + BeautifulSoup/selectolax parse is sufficient for the target audience (static, no-backend, ≤3-page sites); flagged as a known limitation if a submitted "static" site turns out to be a disguised JS-rendered SPA. Page discovery follows same-origin nav/homepage links breadth-first; discovering a 4th distinct page raises `CrawlRejected` with a clear message — **the whole submission is rejected, not silently truncated to 3 pages**. `robots.txt` fetched first via `urllib.robotparser`/`protego`; homepage disallow is a hard reject. Assets (`img`, icons, `@font-face`, stylesheet-referenced backgrounds) are downloaded once per unique URL into `projects/{id}/snapshot/{asset_type}/...` and recorded in `assets`.

## Blueprint Extraction & Generation Pipeline

Extraction aggregates crawled content/nav/headings into markdown prose, then calls a vision-capable OpenRouter model with the logo/hero images to confirm site name, color palette, fonts, and tone — filling the required YAML frontmatter of `design.md`.

**Token usage is now recorded for every AI call (implemented 2026-08-03)**: both `tasks_blueprint.py` (vision call, `purpose="blueprint_extraction"`) and `tasks_generate.py` (agentic loop, `purpose="generation"`) call `token_usage_service.record_usage()` to write a `token_usage_logs` row (see Database Schema) tied to `user_id` and `model_name`. Previously the blueprint-extraction vision call's usage was silently discarded (`_usage` variable, unused) — only the generation step's `prompt_tokens`/`completion_tokens` were captured, on `generation_outputs`, with no link to a user or model name.

**Generation is an agentic tool-calling loop, not a single-shot completion** (revised from the original plan below, per explicit user decision): `site_generator.py` picks a random design-strategy template from `backend/prompts/*.txt` for the tier (currently only `pro` is enabled), and runs a manual OpenAI-style tool-calling loop against **OpenRouter** (model: `anthropic/claude-sonnet-4.5` by default, configurable) — the design-strategy `.txt` file content is used directly as the system prompt (these files are themselves written as agent instructions: "identify the tech stack, build a mental model, ask focused questions..." — an addendum in code overrides the tech-stack-discovery instinct since there's no existing codebase, and constrains output to plain HTML/CSS/JS with Tailwind or Bootstrap via CDN, no build tooling). The model is given three tools — `write_file`, `read_file`, `list_files` — sandboxed (path-traversal-checked) to the project's `generated/{tier}/` output folder, which is pre-populated with the real downloaded images before the loop starts. The loop runs until the model responds with no further tool calls (its final message is the human-readable summary), bounded by `generation_max_iterations`. **Why OpenRouter instead of Anthropic's native Tool Runner**: the user only has an OpenRouter key; OpenRouter speaks an OpenAI-compatible wire format, not Anthropic's native Messages API, so Anthropic SDK features (Tool Runner, `@beta_tool`) can't point at it — the loop is hand-rolled (`_run_agent_loop` in `site_generator.py`) instead.

**Original plan (superseded, kept for context on what changed)**: a single JSON-mode completion producing `{pages, css, js}`, with deterministic post-processing in code for alt text/meta tags/contrast/sitemap. That post-processing (meta/OG tags, alt text, WCAG contrast check, `sitemap.xml` generation) is **not yet implemented** against the new agentic-output path and is a known gap — see `docs/PROGRESS.md`. Each `generation_outputs` row (once DB-wired) should record which `template_id` was used, same as originally planned. Once `basic`/`premium` are enabled later, their prompts should be written so each enabled tier is visibly more polished than the one below it — that ordering rubric is only meaningful once more than one tier is active, so it's deferred rather than enforced today.

## Admin Panel (SQLAdmin)

Auto-registered CRUD for all models; `DesignStrategyTemplate` and `AdminConfig` are the ones admins actively edit. Two things need custom SQLAdmin actions rather than raw generic forms: **manual credit refund** (a button calling `wallet_service.admin_adjust(...)` server-side, not a free-form ledger insert, to keep `credit_wallets.balance` consistent) and **Stripe reconciliation on failed/refunded payments** (same mechanism). SQLAdmin auth reuses the app's existing session/JWT via a custom `AuthenticationBackend` gated on `User.is_admin` — no second login system.

## Auth

Email/password with argon2 hashing, email verification required before first submission/purchase (not before login), self-service password reset (hashed tokens, short TTL) — **still pending**, not yet built. JWT access token (short-lived, in-memory on frontend) + server-side-revocable refresh token (httpOnly cookie) so logout/password-reset can actually invalidate sessions. `AuthIdentity` model is what makes Apple SSO a fast-follow (new enum value + new router) instead of a schema rework.

**Google SSO (implemented 2026-08-03)**: uses the Google Identity Services **ID-token flow**, not a server-side authorization-code redirect. The Angular SPA renders Google's hosted "Sign in with Google" button via the GIS JS library (`GoogleSignInButtonComponent`) using only a Client ID (no client secret on the frontend); Google returns a signed ID token directly to the browser, which POSTs it to `POST /api/v1/auth/google`. The backend verifies the token's signature/audience server-side via the `google-auth` library (`google.oauth2.id_token.verify_oauth2_token`, audience = `REDOWEBS_GOOGLE_CLIENT_ID`) — no redirect URIs, no `state`/CSRF handling, no callback route needed. `auth_service.authenticate_google()` links to an existing user by verified email if present, else creates a new pre-verified user, matching the linking behavior described above. Access tokens are signed with `pyjwt` (`REDOWEBS_JWT_SECRET_KEY`); refresh tokens are opaque random values (`secrets.token_urlsafe`) whose SHA-256 hash is stored in the new `refresh_tokens` table (see Database Schema) — rotated on every `/auth/refresh` call and revoked on `/auth/logout`.

**Ownership + rate limiting (implemented alongside Google SSO)**: `projects.user_id` is now NOT NULL — `POST /api/v1/projects` requires a valid access token (`get_current_user` FastAPI dependency) and `GET /api/v1/projects/{id}` 404s (not 403s, to avoid leaking existence of other users' projects) if the project isn't the caller's. `POST /auth/google` and `POST /projects` are IP-rate-limited via `slowapi` (`app/rate_limit.py`'s shared `Limiter`, keyed by `get_remote_address`), configured via `rate_limit_auth`/`rate_limit_submit` in `config.py`.

## Frontend Routes

`/`, `/auth/*` (signup, login, verify-email, forgot/reset password), `/dashboard`, `/projects/new`, `/projects/:id` (job-status stepper → iframe preview comparison across whatever tiers are currently enabled, with per-tier download button), `/projects/:id/edit` (design.md textarea, Save Draft vs Regenerate-costs-1-credit), `/billing/checkout`, `/account` (wallet balance, transaction history, linked identities). Job polling via a shared RxJS `timer`-based service (3s interval, auto-stops on terminal status) — no WebSockets.

## Testing (per confirmed bar: core logic unit-tested, rest manual)

Unit tests: `wallet_service` (spend success/failure, **concurrent-spend race test**, admin_adjust), `admin_config_service` pricing getters reflect DB changes, Stripe webhook (signature verification, idempotent replay, malformed events), auth/permission gates (unverified-user blocks, admin-only gates, JWT/refresh revocation), weighted template selection (respects `is_active`, weight ratios — assert via mocked `random.choices` args, not statistical sampling). Crawler accuracy and AI output/tier-differentiation quality are verified manually — no automated e2e for subjective AI output.

## Observability & Rate Limiting

Structured JSON logging (structlog/loguru) across backend + Celery workers; Sentry for exception capture and failed-job alerting. `slowapi` (Redis-backed) rate limits on: crawl submission (`POST /projects`), login, register, password-reset request.

## Docker Compose (`standalone/`)

Services: `postgres`, `redis`, `backend` (uvicorn, runs `alembic upgrade head` on startup), `celery-worker`, `celery-beat` (optional, cheap to include for future scheduled housekeeping), `frontend` (Angular dev server), `mailhog` (dev SMTP catcher for verification/reset emails). A shared `storage_data` volume mounts into both `backend` and `celery-worker` at the same path — the one place local-disk storage needs care, since the API serves downloads while the worker writes generated output.

## Build Order / Milestones

1. **Scaffolding** — repo skeleton, Compose stack boots empty, Alembic wired.
2. **Core loop (highest risk, build first)** — stub auth, crawler → blueprint → 3-tier generation working end-to-end with a bare Angular submit/poll/preview flow. No credits, no admin, no Stripe. This proves the product concept.
3. **design.md editing & regeneration** — free (no credit gate yet) to validate versioning mechanics.
4. **Credit/wallet system** — `wallet_service` with row-locking spend (TDD, tests first), signup grant, wire generation/regeneration to spend real credits, wire the pre-check/no-charge-on-reject path.
5. **Downloads + AdminConfig** — tier-cost spend, folder assembly, download endpoint/UI.
6. **Auth hardening** — real email verification, password reset, Google OAuth, JWT+refresh sessions.
7. **Stripe billing** — Checkout Session, webhook + idempotency (tests alongside), credit-pack purchase UI.
8. **Admin panel** — SQLAdmin mount, all ModelViews, custom refund action.
9. **Observability & rate limiting** — structlog, Sentry, slowapi on the flagged endpoints, confirm submission_logs works end to end.
10. **Polish** — SEO/accessibility verification pass, tier-differentiation prompt tuning, UI polish, any deferred tests.

This order front-loads the one genuinely uncertain piece — does crawl→blueprint→AI-generation actually produce good, differentiated output — before investing in payments/auth/admin plumbing that's comparatively well-understood engineering.

## Verification

- Milestone 2 end-to-end check: submit a real small static site's URL, confirm job progresses through all stages, confirm `design.md` has valid frontmatter + sensible prose, confirm all 3 tier previews render and are visibly different in polish (Pro > Premium > Basic).
- Milestone 4: run `pytest backend/tests/unit/test_wallet_service.py` including the concurrent-spend test; manually attempt two rapid download clicks against a low balance to confirm only one succeeds.
- Milestone 6: use Stripe CLI (`stripe listen --forward-to localhost:.../billing/webhook`) to fire test webhook events, confirm idempotent replay doesn't double-credit.
- Milestone 8: confirm a non-admin JWT is rejected at `/admin`, confirm the custom refund action updates both the ledger and `credit_wallets.balance` consistently.
- Full run: `docker compose -f standalone/docker-compose.yml up`, exercise the complete user journey (signup → verify → submit → preview → regenerate → buy credits → download) manually before calling v1 done.
