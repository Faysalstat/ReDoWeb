# Logging — remaining to-do

Follow-up to [LOGGING.md](LOGGING.md). Steps 1–4 of the $0 logging plan are done (correlation fields, JSON events, redaction, Axiom shipper, `ai.call.*` events). This file lists what's left, in order. Each step can ship on its own. Tick boxes as you go and move finished items into LOGGING.md → *Status*.

Two rules for every step:
- Stay on free tiers. Nothing here should add a monthly cost.
- Never `print()`. Use `logger.<level>("…", extra={"event": "area.thing", ...})` with a stable dotted event name, and add new names to the catalogue in LOGGING.md.

---

## A. Account setup (manual, ~20 min, no code)

- [ ] **Axiom** (30-day log archive)
  1. Sign up at axiom.co on the free **Personal** plan.
  2. Create a dataset named `redowebs`.
  3. Settings → API tokens → create a token with **ingest** permission on `redowebs` only.
  4. On Railway (backend service), set `REDOWEBS_AXIOM_TOKEN=<token>` and redeploy.
  5. Check: open Axiom, run `['redowebs'] | take 20`. Lines should appear within ~10s of any API call.
- [ ] **Axiom monitors** (free alerts, email). Create three:
  - Failed jobs: `['redowebs'] | where event == "job.finished" and status == "failed"`, count > 0 over 15 min.
  - OpenRouter trouble: `['redowebs'] | where event == "ai.call.retry"`, count > 20 over 15 min.
  - Daily AI spend: `['redowebs'] | where event == "ai.call.completed" | summarize sum(cost_usd)` over 1 day, above your budget.
- [ ] **Sentry**
  1. Sign up on the free **Developer** plan.
  2. Create two projects: `redowebs-backend` (Python/FastAPI) and `redowebs-frontend` (Angular).
  3. Keep both DSNs for step B.
- [ ] **UptimeRobot**: sign up (free). Wait for step E before adding the monitor.

---

## B. Sentry error tracking (code)

**Backend**
- [ ] Add `sentry-sdk[fastapi]` to `backend/requirements.txt`.
- [ ] Add settings to `backend/app/config.py`: `sentry_dsn: str = ""` and `sentry_traces_sample_rate: float = 0.0`.
- [ ] New `backend/app/observability/sentry.py` with `init_sentry(service)`:
  - Return early if `sentry_dsn` is empty, so local dev and tests stay no-ops.
  - Call `sentry_sdk.init(dsn, environment=logging_config.resolve_environment(), release=<RAILWAY_GIT_COMMIT_SHA[:12]>, send_default_pii=False, traces_sample_rate=settings.sentry_traces_sample_rate, before_send=_scrub)`.
  - `_scrub` runs `observability.redaction.redact_value` over the event's `request`, `extra` and `breadcrumbs`.
  - Set tag `service` to "api" or "worker".
- [ ] Call `init_sentry("api")` in `main.py` right after `configure_logging`, and `init_sentry("worker")` in `queue_worker.py`'s `__main__`.
- [ ] In `queue_worker._run_job`'s `except`, before `logger.exception`:
  - Open `sentry_sdk.new_scope()` (or `push_scope()` on older SDKs).
  - Set tags `trace_id`, `task`, `project_id` and `tier` from `log_context.current()`.
  - Call `capture_exception(exc)`.
- [ ] In `observability/middleware.py`'s `except`, set the Sentry tag `request_id`. The FastAPI integration captures the error itself.
- [ ] Railway env: set `REDOWEBS_SENTRY_DSN` on the backend service.
- [ ] Test: unit test that `init_sentry` does nothing without a DSN, and that `_scrub` masks a JWT in `extra`.

**Frontend**
- [ ] `npm i @sentry/angular` in `frontend/`.
- [ ] Put the DSN next to the API base URL in `frontend/src/app/core/api-config.ts` (empty = disabled). A Sentry DSN is safe to ship to the browser.
- [ ] In `frontend/src/main.ts`, call `Sentry.init({ dsn, environment, release })` before bootstrap, only if a DSN is set.
- [ ] In `frontend/src/app/app.config.ts`, add `{ provide: ErrorHandler, useValue: Sentry.createErrorHandler() }`.
- [ ] New `frontend/src/app/core/request-id.interceptor.ts`, registered **first** in `withInterceptors([...])`:
  - Add an `X-Request-ID` header (`crypto.randomUUID().replaceAll('-', '')`) to calls to our API only, not PayPal.
  - On a 5xx or status 0 (network error), call `Sentry.captureMessage` with tags `request_id` and `url`. The backend's logs carry the same id as `trace_id`.
- [ ] Optional: on error toasts, show "Reference: <first 8 chars of request id>" so users can quote it to support.
- [ ] Report the money path explicitly: PayPal SDK load failure in `paypal-sdk.loader.ts`, and a failed capture in the checkout `onApprove`.

---

## C. Log the important business events (code)

Add one `logger` per module (`logging.getLogger(__name__)`) and the events below. Levels: INFO = done, WARNING = degraded or rejected, ERROR = failed. IDs come from context automatically; only pass what's specific to the event.

**Money first**
- [ ] `services/wallet_service.py`:
  - `spend()` → `wallet.spend` (amount, idempotency_key, balance_after).
  - Already-spent key → `wallet.spend.replayed` (INFO).
  - Insufficient balance → `wallet.spend.insufficient` (WARNING).
  - `grant_purchase_credits()` → `wallet.grant` (purchase_id, credits).
  - `admin_adjust()` → `wallet.admin_adjust` (amount, admin_user_id).
- [ ] `services/billing_service.py`:
  - `create_order()` → `paypal.order.created` (purchase_id, pack, amount).
  - `_apply_capture()` → `paypal.capture.completed`, or `paypal.capture.mismatch` (WARNING) on an amount/currency mismatch.
  - `handle_webhook_event()` → `paypal.webhook.received` (event_type, result).
  - `recheck_purchase()` → `paypal.recheck` (status before/after).
  - `mark_refunded()` → `paypal.refund.detected` (WARNING).
- [ ] `routers/billing.py` webhook: signature verification failed → `paypal.webhook.rejected` (WARNING). This is the alert to watch.
- [ ] `routers/downloads.py`: purchase → `purchase.completed` (tier, credits). Full-site and SEO start → `action.started` (action, tier).

**Auth**
- [ ] `routers/auth.py` / `services/auth_service.py`:
  - `auth.login.succeeded` (provider, new_user: bool)
  - `auth.login.failed` (WARNING, reason, no email)
  - `auth.refresh.failed` (WARNING)
- [ ] `auth/dependencies.py`: `require_admin` refusing a user → `auth.admin.forbidden` (WARNING).

**Pipeline**
- [ ] `routers/projects.py` submit → `project.submitted` (domain only, not the full URL query; tier_keys).
- [ ] `workers/tasks_crawl.py` / `services/crawl_service.py`:
  - `crawl.completed` (pages, assets, duration_ms)
  - `crawl.rejected` (WARNING, reason such as too many pages or robots)
  - `crawl/fetch.py`: per page → `crawl.page.fetched` at **DEBUG** (url, status, bytes, ms)
- [ ] `workers/tasks_blueprint.py`:
  - `blueprint.completed` (sections found, duration_ms)
  - Cost gate paused → `blueprint.cost_gate.paused` (estimate_usd)
  - Fan-out → `generation.enqueued` (tiers)
- [ ] `ai/blueprint_review.py`: merge dropped a model-invented key, or the anti-fabrication check rejected text → `blueprint.review.rejected_output` (WARNING, section, reason). Vision meta call fell back to heuristics → `blueprint.meta.fallback` (WARNING).
- [ ] `ai/site_generator.py`:
  - `generation.template.selected` (template)
  - Iteration limit hit → `generation.iteration_limit` (WARNING, iterations, last finish_reason)
  - `generation.completed` (files, tokens, cost)
- [ ] `workers/tasks_generate.py` / `tasks_full_site.py`: tier failed → `tier.failed` (ERROR, error_type), with the user-facing message kept separate.
- [ ] `services/job_progress.py`:
  - Drop the hand-built `[seo job=… project=… tier=…]` prefix from `context`; the worker's scope already adds those fields.
  - Add `extra={"event": "seo.step"}` and `{"event": "seo.activity"}` to its lines.
  - Update `tests/test_job_progress.py` if it asserts on the prefix.

**Rate limiting**
- [ ] `main.py`: wrap `_rate_limit_exceeded_handler` so it logs `ratelimit.exceeded` (WARNING, route) before returning the 429.

**Startup**
- [ ] `main.py` startup hook, and the start of `queue_worker`: `app.started` with release, env, db_pool_size, payments_mode and paypal_env. **No secrets.**

Done when: a test project submitted locally shows, under one `trace_id`, `project.submitted → job.started(run_crawl) → crawl.completed → … → generation.completed → job.finished` with no gaps.

---

## D. Admin audit log (code + migration)

Today `updated_by_admin_id` columns only remember *who changed it last*. This adds full history.

- [ ] New model `backend/app/models/admin_audit_event.py`, table `admin_audit_events`:
  - `id` (uuid pk), `admin_user_id` (fk users), `action` (str 64, e.g. `tier.update`)
  - `entity_type` (str 32), `entity_id` (str 64)
  - `before` (jsonb, nullable), `after` (jsonb, nullable)
  - `request_id` (str 64, nullable), `created_at` (server default now)
  - Index on `(entity_type, entity_id)` and on `created_at`.
- [ ] Alembic migration for it, then `alembic upgrade head` (locally and on Railway).
- [ ] New `backend/app/services/audit_service.py` with `record(db, admin, action, entity_type, entity_id, before, after)`:
  - Adds the row **without committing**, so it lands in the caller's transaction.
  - Fills `request_id` from `log_context.current()`.
  - Logs `admin.audit` at INFO.
- [ ] Call it from every admin mutation:
  - tiers (update, activate)
  - credit packs
  - model config (tier model, vision model)
  - model pricing
  - cost gate config
  - prompt templates (upload, enable/disable, delete)
  - credit adjustments (`admin_credits_service.issue_adjustment`)
  - payment actions (re-check, take back credits, mark failed)
  - `scripts/promote_admin.py` (admin_user_id = the promoted user, action `admin.promote`)
- [ ] New `GET /api/v1/admin/audit-events` endpoint, paginated, filterable by entity_type, entity_id and admin, gated by `require_admin`.
- [ ] Angular admin page "Audit log" under `frontend/src/app/features/admin/`: a table with time, admin, action, entity, and before/after shown as a diff or JSON.
- [ ] Tests:
  - `record()` writes nothing extra if the caller rolls back.
  - Each admin router writes exactly one event per change.
  - Non-admins get 403 on the list endpoint.

---

## E. Worker heartbeat + readiness check (code + migration)

Catches the "API alive, worker hung" case. `start.sh` restarts a *crashed* process, not a *stuck* one.

- [ ] New table `worker_heartbeats` (`worker_id` pk, `last_seen_at`, `current_task` nullable, `current_queued_job_id` nullable) plus a migration.
- [ ] `queue_worker.run_worker_loop`: upsert its row every ~30s while idle. Set `current_task` when a job starts and clear it when it ends.
  - A long AI call blocks the loop, so do the upsert from a small daemon thread with its own session, not from the loop.
- [ ] New `GET /health/ready` in `main.py` (keep `/health` as is for Railway's own healthcheck):
  - 200 when a `SELECT 1` succeeds **and** some heartbeat is newer than 2 minutes.
  - Otherwise 503 with `{"db": bool, "worker_seen_seconds_ago": n}`.
  - Already quiet in logs (the `/health` prefix).
- [ ] Optional: in the same check, report `queued_jobs` stuck in `running` for over 30 minutes as `stuck_jobs: n` (don't fail on it).
- [ ] UptimeRobot: add an HTTP(s) monitor on `https://<backend-domain>/health/ready`, 5-minute interval, email alert.
- [ ] Test the endpoint with a fresh vs. stale heartbeat.

---

## F. Real client IP behind Railway (check, then maybe fix)

`routers/projects.py` stores `request.client.host` as `submitted_ip`. That is the abuse/DMCA record this project relies on instead of domain verification.

- [ ] Check: in the production DB, run `SELECT submitted_ip, created_at FROM projects ORDER BY created_at DESC LIMIT 5;`.
  - Public IPs (your own home IP among them) → nothing to do; tick and close.
  - Private/internal addresses (`10.x`, `100.64.x`, `172.16–31.x`) → Railway's proxy IP. Fix below.
- [ ] Fix: in `backend/start.sh`, add `--proxy-headers --forwarded-allow-ips="*"` to the uvicorn line. This is safe only because Railway's edge is the sole way in; don't copy the flag to a setup with a public port.
- [ ] Re-check with a new submission.

---

## G. Housekeeping

- [ ] After each step above, update LOGGING.md (*Status* + event catalogue) and `docs/PROGRESS.md`.
- [ ] Once Sentry is live, add a line to CLAUDE.md's settled decisions: free-tier Sentry + Axiom, `trace_id` = `X-Request-ID`, no paid observability without sign-off.
- [ ] Review monthly: Sentry usage page (stay under 5,000 errors), and Axiom usage (expect ~1 GB per 100 projects/day). If Sentry nears the limit, add `ignore_errors`/sampling rather than upgrading.

## Suggested order
**A → B → C (money and auth part) → F → E → C (pipeline part) → D.** Set up the accounts first, then error alerts. Money and auth logging comes next because it matters most for disputes. The IP check is a 2-minute query. The audit table is last because it's the largest change.
