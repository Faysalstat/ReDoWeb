# Logging & production log tracking

Added 2026-10-06. This is the **$0/month** setup: Railway's log view for live and recent logs, an optional free Axiom archive for 30 days, and (planned) Sentry free for errors. The full plan and cost estimate are in the "Cheapest production logging plan" (steps 1–4 are done; see *Status* below).

## How it works

- **One setup for both processes**: `backend/app/logging_config.py`. `configure_logging(service="api")` runs in `main.py`, and `configure_logging(service="worker", worker_id=…)` runs in `queue_worker.py`. Everything goes to stdout (Railway treats stderr as error-level).
- **Correlation fields**: `backend/app/observability/context.py`.
  - One mutable dict lives in a ContextVar.
  - `scope(**fields)` opens a scope; the request middleware and the worker each open one per request or job.
  - `bind(**fields)` adds fields inside the current scope (e.g. `get_current_user` binds `user_id`). It is a no-op outside a scope.
  - Why a dict and not one ContextVar per field: FastAPI runs sync dependencies on a *copy* of the context, so a plain `ContextVar.set()` there would never reach the request's access line.
  - Thread pools: use `submit_with_context(executor, fn, ...)` (see `blueprint_review.py`), or pool threads lose the fields.
- **Trace across API → queue → worker**:
  1. `RequestContextMiddleware` (`observability/middleware.py`) takes or makes `X-Request-ID`, uses it as `trace_id`, and echoes it in the response (CORS exposes it).
  2. `queue.enqueue()` copies `trace_id` into the payload under `_trace_id`.
  3. `queue_worker` pops it before calling the task and opens a scope with `trace_id`, `queued_job_id`, `task`, `project_id`, `tier` and `job_id`.
  4. The next stage enqueued from inside a task inherits the same `trace_id`, so **one submission's whole pipeline (crawl → blueprint → every tier → full-site/SEO) shares one `trace_id`**. A purchase action started later carries that request's own id.
- **Redaction**: `observability/redaction.py` runs on every message, traceback and extra field.
  - Masks JWTs, `Bearer …`, OpenRouter keys, and `access_token=`/`client_secret=`-style pairs.
  - Masks any field whose name ends in token/secret/password/cookie/authorization/api_key/signature.
  - Token *counts* (`prompt_tokens`) are not masked.
- **Noise control**:
  - `httpx`, `httpcore`, `sqlalchemy.engine`, `PIL` and `urllib3` are set to WARNING.
  - Successful `/health`, `/preview/*` and status-poll (`GET /api/v1/projects/{project_id}`) requests log at DEBUG only.
  - uvicorn's access log is off in deploys (`--no-access-log` in `start.sh` and the Dockerfile) because the middleware writes a richer line. Local dev still shows both, which is harmless.

## Event shape (JSON mode)

```json
{"timestamp": "...", "level": "info", "logger": "app.ai.openrouter", "message": "chat_completion #4 ... ok",
 "service": "worker", "env": "production", "release": "3f5134c1abcd", "worker_id": "w2",
 "trace_id": "...", "project_id": "...", "tier": "pro", "task": "generate_tier", "job_id": "...",
 "event": "ai.call.completed", "model": "...", "prompt_tokens": 1200, "completion_tokens": 3400,
 "cost_usd": 0.002, "finish_reason": "tool_calls", "duration_ms": 8421}
```

To add a field to one line, use `logger.info("…", extra={"event": "x.y", "duration_ms": …})`. Every non-standard record attribute becomes a JSON field. Don't name extras `message`, `asctime` or `args`.

### Event catalogue (stable names, filter on these)

| event | where | level |
|---|---|---|
| `http.request` | middleware: method, route (template), path, status, duration_ms | INFO; DEBUG for quiet routes; WARNING for 4xx except 401/404; ERROR for 5xx |
| `http.unhandled_exception` | middleware, with traceback + error_type | ERROR |
| `worker.started` | queue_worker | INFO |
| `job.started` | queue_worker, with queue_wait_ms | INFO |
| `job.finished` | queue_worker, status=succeeded/failed, duration_ms (+ traceback when failed) | INFO / ERROR |
| `ai.call.started` | openrouter_client, with prompt previews | DEBUG only |
| `ai.call.completed` | openrouter_client: call_type, model, tokens, cost_usd, finish_reason, duration_ms | INFO |
| `ai.call.retry` | openrouter_client: status or error_type, attempt, delay_s | WARNING |
| `ai.call.failed` | openrouter_client: error_type, error (≤500 chars), status | WARNING (the caller decides if it's fatal) |
| `billing.order_created` | billing_service: purchase_id, user_id, paypal_order_id | INFO |
| `billing.capture_completed` | billing_service: credits granted (browser capture, webhook or reconciler) | INFO |
| `billing.capture_pending` | billing_service: reason (`transient`, PayPal `PENDING`, …) — purchase left pending on purpose | INFO / WARNING |
| `billing.capture_failed` | billing_service: issue (e.g. `INSTRUMENT_DECLINED`), status | INFO / WARNING |
| `billing.amount_mismatch` | billing_service: PayPal captured money that didn't match the snapshot — **resolve by hand** | WARNING |
| `billing.refund_marked` | billing_service: refund/reversal recorded, credits not taken back | WARNING |
| `billing.dispute` | billing_service: dispute_id, dispute_status, matched | WARNING |
| `billing.webhook_processed` | routers/billing: paypal_event, result | INFO |
| `billing.webhook_rejected` | routers/billing: reason `bad_signature` / `verify_unavailable` / `bad_json` | WARNING |
| `billing.reconciled` / `billing.reconcile_error` / `billing.reconcile_run` | workers/billing_reconcile: a stale pending purchase resolved / couldn't be checked / run summary | INFO / WARNING |
| *(SEO job lines)* | `services/job_progress.py` (`app.jobs` logger) | as before |

Prompt text never goes into the log stream at INFO. The full model conversation stays in `_debug_trace*.json` next to the generated output.

## Settings (env vars, `REDOWEBS_` prefix)

| var | default | notes |
|---|---|---|
| `REDOWEBS_LOG_FORMAT` | `text` | `json` on Railway (already set) |
| `REDOWEBS_LOG_LEVEL` | `INFO` | `DEBUG` shows prompt previews and quiet routes |
| `REDOWEBS_ENVIRONMENT` | *(empty)* | Empty = Railway's `RAILWAY_ENVIRONMENT_NAME`, else `development` |
| `REDOWEBS_AXIOM_TOKEN` | *(empty)* | Empty = no shipping. Use an Axiom **ingest-only** API token |
| `REDOWEBS_AXIOM_DATASET` | `redowebs` | Create the dataset in Axiom first |
| `REDOWEBS_AXIOM_INGEST_URL` | `https://api.axiom.co/v1/datasets/{dataset}/ingest` | Change only if Axiom tells you to use a regional/edge endpoint |

`release` comes from Railway's `RAILWAY_GIT_COMMIT_SHA` (first 12 characters) automatically.

## Watching logs in production

**Railway (live, last 7 days on Hobby).** In the service's *Logs* tab:
- `@level:error`: everything that broke.
- `@trace_id:<id>`: one submission end to end. Get the id from any line for that project, or from the response's `X-Request-ID`.
- `@project_id:<uuid>`: everything for a project (worker lines; API lines carry it once handlers bind it).
- `@event:ai.call.retry` / `@event:ai.call.failed`: OpenRouter trouble.
- `@event:job.finished @status:failed`: failed pipeline stages.
- `@event:billing.amount_mismatch`, `@event:billing.dispute`, `@event:billing.webhook_rejected`: payments needing a human (good Axiom monitor candidates).

**Axiom (30 days, free Personal plan: 500 GB/mo ingest, far above our ~1 GB/mo).** Setup, once:
1. Sign up (free).
2. Create dataset `redowebs`.
3. Create an API token with ingest permission for it.
4. Set `REDOWEBS_AXIOM_TOKEN` on the Railway backend service and redeploy.

Shipping runs in a background thread in each process. It batches every 5s, uses a bounded queue, and drops lines rather than blocking. Problems print one `axiom: …` warning line to stdout at most once a minute. Railway's own log stays the complete copy.

Useful APL queries:
```
['redowebs'] | where event == "job.finished" and status == "failed" | summarize count() by task, bin_auto(_time)
['redowebs'] | where event == "ai.call.completed" | summarize sum(cost_usd), sum(prompt_tokens), sum(completion_tokens) by model, bin(_time, 1d)
['redowebs'] | where trace_id == "<id>" | sort by _time asc
['redowebs'] | where event == "http.request" and status >= 500 | summarize count() by route
```

Free alerts are set up as Axiom monitors on: failed jobs greater than 0 in 15 minutes, an `ai.call.retry` spike, and a daily `cost_usd` over budget.

## Status

- **Done (2026-10-06)**:
  - Foundation (context, JSON events, redaction, quiet loggers)
  - Axiom shipper
  - Correlation (middleware, trace via queue, worker job scope, thread-pool propagation)
  - OpenRouter `print()` calls replaced with `ai.call.*` events
  - Tests: `backend/tests/test_logging.py`
- **Not yet** (step-by-step instructions in [logging-todo.md](logging-todo.md)):
  - Sentry free (backend + Angular `ErrorHandler`/interceptor sending `X-Request-ID`)
  - Instrumenting money/auth/crawler/blueprint modules with events
  - `admin_audit_events` table
  - Worker heartbeat + `/health/ready` for UptimeRobot
  - Proxy-IP check for `projects.submitted_ip` behind Railway
