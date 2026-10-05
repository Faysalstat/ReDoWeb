# ReDoWebs — Product Requirements Document (v1)

## 1. Problem & Goals

Small businesses and individuals often have an outdated static website (or a simple WordPress-style site) that looks dated, has weak SEO/accessibility, and would cost real money to have redesigned by a professional. ReDoWebs lets an owner submit their existing site's URL and receive AI-generated, modernized redesigns across one or more admin-configurable quality tiers (e.g. a lightly polished Basic refresh up to a fully modern, visually striking Pro rebuild) that preserve their original content, brand identity, and business intent while fixing copy quality, SEO, accessibility, and dated UI patterns.

**Primary goal for v1**: prove that the crawl → extract blueprint → AI-generate-tier pipeline reliably produces a genuinely usable redesign for small, static (≤3-page) websites, and that users will pay credits to download the result. Build/test phase currently validates this with a single `pro` tier before enabling additional tiers.

## 2. Target Users

- Small business owners / solo operators with an existing simple static website who want a modern redesign without hiring a designer or developer.
- Users are not expected to be technical — they interact via URL submission, visual previews, and a plain-text blueprint editor, not code.

## 3. Scope

### In scope (v1)
- Crawling static/simple websites with **no server-rendered backend**, capped at **3 pages** (sites with more are rejected outright with a clear message, not silently truncated).
- Full blueprint extraction: content, navigation, branding assets (logo, images, icons, fonts, color palette), metadata, layout hierarchy — stored as a semi-structured `design.md` (required YAML frontmatter + freeform markdown body).
- AI-driven correction of spelling/grammar/readability, SEO and accessibility optimization, and modernized responsive redesign — while preserving original brand identity, business information, and intent.
- **Tiered outputs per submission, generated from the same blueprint** using randomly-selected, admin-managed prompt-strategy variants per tier. Tiers are a **dynamic, admin-manageable list** (not a fixed Basic/Premium/Pro enum) — admins can enable/disable, rename, reorder, and price individual tiers; only enabled tiers are generated for a submission. When multiple tiers are enabled, each should be visibly, meaningfully more polished than the one below it. **Current build/test phase runs only a single `pro` tier** while the generation approach and prompts are being validated — `basic`/`premium` exist as disabled placeholders to enable later.
- Unlimited preview of all enabled tiers, for any project, at any time.
- Manual editing of `design.md` (plain text) with regeneration.
- A unified credit wallet: 3 free credits on signup; every generation or regeneration costs 1 credit (same pool, no special-casing); downloading costs tier-specific, admin-configurable credits (cost lives on each tier's own row, not a separate fixed mapping).
- One-time PayPal purchases (PayPal account or card) of admin-configurable credit packs, each with its own price (no subscriptions).
- Download only after sufficient credits are spent, producing a uniquely-named folder: `design.md`, HTML pages, global CSS, global JS, an `images/` folder of locally-referenced downloaded assets, and a generated `sitemap.xml`.
- Auth via email/password (with email verification and password reset) and Google SSO.
- A mandatory ToS acknowledgment at submission ("I own or am authorized to redesign this site"), with every submission logged for abuse/DMCA response.
- Rate limiting on crawl submissions independent of credit-gating.
- Admin panel: manage users, prompt-strategy templates, credit/pricing configuration, token usage analytics, payments, and generation jobs.
- Structured logging and error-tracking/alerting on failed jobs.
- Docker-based local development matching the repo's mandated `frontend/` / `backend/` / `docs/` / `standalone/` layout.

### Out of scope (v1)
- JS-rendered single-page applications / any site requiring a headless browser to render content.
- WordPress-API-specific ingestion (WordPress sites are only handled to the extent they present as simple static HTML).
- Sites exceeding 3 pages.
- Apple SSO (planned fast-follow; data model supports adding it without rework).
- Subscription billing.
- Automatic credit-refund reconciliation on failed/refunded payments (handled manually via admin panel).
- User-facing display of raw AI token usage (internal/admin analytics only).
- A structured (non-markdown) blueprint editing UI.
- Multi-LLM-per-tier generation (tiers differ by prompt strategy, not by underlying model).
- Domain-ownership verification before crawling (mitigated instead by a ToS checkbox and logging).
- Multi-currency support (USD/PayPal only).
- Internationalization/localization.

## 4. Core User Journey

1. User signs up (email/password, verifies email; or Google SSO, pre-verified) and receives 3 free credits.
2. User submits a URL and accepts the ToS ownership checkbox.
3. System validates the site is accessible and ≤3 pages; on failure, submission is rejected with a clear message and no credit is charged.
4. On success, 1 credit is spent; the site is crawled, a blueprint (`design.md`) is extracted, and a redesign is generated for each currently-enabled tier in the background. The user sees live progress ("Crawling → Extracting blueprint → Generating [enabled tiers] → Done").
5. User previews all enabled tiers side by side, unlimited times.
6. Optionally, the user edits `design.md` and regenerates (1 credit per regeneration), reviewing new versions.
7. When satisfied, the user spends the tier-appropriate credits to unlock and download that tier's full source folder. If the wallet balance is insufficient, the user purchases a credit pack via PayPal (account or card).
8. The project and all its downloaded/purchased tiers remain accessible from the user's account dashboard indefinitely.

## 5. Functional Requirements

- **FR1** — Crawl a submitted URL respecting `robots.txt`; detect and reject inaccessible sites (non-200 status, robots disallow, login/auth walls) and sites with more than 3 discoverable pages, each with a distinct, clear user-facing message.
- **FR2** — Extract a blueprint capturing content, nav structure, branding assets (logo/images/icons/fonts/palette), metadata, and layout hierarchy into `design.md`, with a required frontmatter block (site name, colors, logo path, fonts) and freeform prose body.
- **FR3** — Generate a redesign per *enabled* tier from randomly-selected active prompt-strategy templates for that tier; log which template produced each output. Tiers themselves are admin-manageable (add/rename/enable/disable/reorder/price), not a fixed set.
- **FR4** — Correct grammar/spelling, improve readability, and optimize for SEO (meta/OG tags, sitemap) and accessibility (semantic HTML, alt text, WCAG AA contrast) in all generated output, while preserving original brand identity and business information.
- **FR5** — Allow unlimited preview of generated tiers without consuming credits.
- **FR6** — Allow manual editing of `design.md` and regeneration, consuming 1 credit per regeneration and retaining full version history.
- **FR7** — Maintain a per-user credit wallet with an auditable transaction ledger; grant 3 credits on signup; debit 1 credit per generation/regeneration; debit tier-specific, admin-configurable credits per download; prevent race conditions on concurrent spend attempts.
- **FR8** — Sell admin-configurable credit packs via one-time PayPal checkout (PayPal account or card); credit the wallet on server-side capture, with a signature-verified webhook as a backup, crediting each purchase exactly once.
- **FR9** — Block source-code download until sufficient credits have been spent for the selected tier; on success, produce a folder containing `design.md`, HTML pages, global CSS/JS, an `images/` folder with locally-referenced assets, and `sitemap.xml`.
- **FR10** — Authenticate users via email/password (with verification and password reset) and Google SSO; require email verification before first submission or purchase.
- **FR11** — Require ToS acknowledgment at submission time and log every submission (user, URL, IP, timestamp, acknowledgment) for abuse response.
- **FR12** — Rate-limit crawl submissions per user/IP independent of credit balance.
- **FR13** — Provide an admin interface to manage users, prompt-strategy templates (add/disable/weight), credit costs and pricing, token usage analytics, payments, and generation job status — including a controlled manual credit-refund action.
- **FR14** — Track AI token usage per job/user for internal cost analytics.
- **FR15** — Retain purchased/generated projects in the user's dashboard for ongoing access and re-download.

## 6. Non-Functional Requirements

- **Scale**: v1 targets tens to low-hundreds of active users and a handful of concurrent generation jobs — no auto-scaling or queue sharding required.
- **Reliability**: transient job failures (timeouts, rate limits) auto-retry with backoff; definitive failures fail fast with no retry and no credit charge.
- **Security**: password hashing (argon2), short-lived JWT access tokens with revocable refresh tokens, PayPal webhook signature verification, no plaintext secrets.
- **Observability**: structured JSON logging across backend and workers; error tracking/alerting (e.g., Sentry) on unhandled exceptions and failed jobs.
- **Testing bar**: automated unit tests for credit/wallet logic, tier pricing, PayPal capture/webhook handling, and auth/permission checks; crawler accuracy and AI output quality verified manually.
- **Accessibility/SEO of generated output**: semantic HTML5, per-page meta title/description and Open Graph tags, AI-generated alt text, WCAG AA contrast, generated sitemap.
- **Deployment**: fully reproducible via Docker Compose for local development; no production infrastructure assumptions locked in beyond a general AWS target.

## 7. Success Metrics (v1)

- A submitted small static site reliably produces three tiers that are visually and qualitatively distinguishable from one another (Pro > Premium > Basic), validated through manual review during development.
- End-to-end journey (signup → submit → preview → regenerate → purchase → download) completes without manual intervention in normal conditions.
- Credit ledger remains consistent under concurrent spend attempts (verified by automated test).
- No download is ever served without the corresponding credit deduction having succeeded.

## 8. Assumptions

- Vision-capable OpenRouter model calls (same provider as text generation) are sufficient for logo/color/font extraction in v1; no dedicated computer-vision service is used.
- Credit pack sizes and the $-per-credit rate will need reasonable initial defaults at launch, refined post-launch via the admin panel.
- Regeneration always creates a new blueprint version rather than overwriting, so history is preserved and comparable.
- A single currency (USD) and PayPal as sole payment processor are sufficient for v1's audience (changed from Stripe on 2026-10-05, before any Stripe code was built).

## 9. Open Risks

- **Legal/ownership exposure**: since any user can submit any public URL, the platform could be used to clone a site the submitter doesn't own or control. Mitigated in v1 by a mandatory ToS checkbox and submission logging (not by technical ownership verification) — this is a deliberate, lower-friction trade-off that carries residual legal risk the business accepts for v1.
- **Crawler robustness**: markup quality and asset/palette/font extraction reliability will vary across real-world sites; expect iteration rather than a fully solved heuristic on day one.
- **AI cost/rate limits at production scale**: v1 uses GPT-4o-mini via OpenRouter for development/testing; production model choice and per-generation cost should be revisited before wider launch.
- **Tier differentiation quality**: "Pro must visibly beat Premium must visibly beat Basic" is enforced through prompt engineering and will require empirical tuning after the pipeline is functional, not a guaranteed property of the initial prompts.
- **Local disk storage**: adequate for v1/single-server operation; will need revisiting (S3 migration) before scaling beyond a single backend instance.

---

*Companion document: the technical implementation plan (architecture, database schema, API surface, Celery task design, and build-order milestones) is maintained separately as the engineering execution plan derived from this PRD.*
