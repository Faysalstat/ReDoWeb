# Plan: admin panel for payments, refunds and tier pricing

> **Status (2026-10-05): implemented** (after one review pass, see "Review fixes" at the end). Not yet run against a live Postgres (migration `c4e8a2d6f1b9` still to apply) or the PayPal sandbox. See docs/PROGRESS.md. Decisions confirmed with the user on 2026-10-05: the payment mode is **read-only** in the UI; admins **don't issue PayPal refunds** from the panel; tiers and packs move onto **one Tiers & pricing page**; build **all** of A–F.

## Context

The PayPal payments feature (`docs/paypal-payments-plan.md`) added a Credit packs page, editable download costs and a purchases table on Earnings. What it didn't add was any way for an admin to *operate* payments:

- A purchase whose webhook never arrives stays `pending` forever. That is always the case locally.
- A refunded purchase is only marked; taking the credits back is a manual adjustment that isn't linked to the purchase.
- Admins can't see which payment mode is running (test / sandbox / live).
- The user and project pages don't show purchases or paid tiers.
- Tier settings are spread across Model config, and the PRD's "rename / reorder" isn't possible.

This plan closes those gaps.

**Settled constraints:**

- Refunds are made in the PayPal dashboard, never from this app (PRD: refund reconciliation is manual).
- The payment mode stays an `.env` setting. A UI toggle into test mode would be a "free credits" switch.
- Every admin action records who did it and is safe to repeat (idempotent).

## A. Payments page (new `/admin/payments`)

Purchases move off Earnings; Earnings keeps only the revenue figures.

**Status banner.** One line at the top: **Test mode** / **PayPal sandbox** / **PayPal live**, plus:

- PayPal keys configured ✓/✗
- Webhook ID set ✓/✗
- a red warning if `REDOWEBS_PAYMENTS_MODE=mock` is set but ignored because the frontend URL isn't localhost.

It comes from a new `GET /admin/payments/status`, built from `mock_gateway.is_requested()` / `is_active()`, `paypal_client.is_configured()` and `settings.paypal_webhook_id`. The endpoint never returns a secret.

**Table.** Extend the existing `GET /admin/purchases` with:

- `email` (search on the buyer's email)
- `include_mock` (default `false`)

Existing filters `status` and `source` stay. An explicit `source=mock` overrides `include_mock=false`, so the two filters can't silently return nothing. Columns: date, buyer, pack, credits, amount, source, status. A "Show test purchases" toggle is off by default.

**Detail panel.** New `GET /admin/purchases/{id}`, showing:

- buyer, pack name, credit/price snapshot
- PayPal order and capture IDs
- note
- who resolved it, and when
- `refunded_at`
- every ledger row with this `related_purchase_id`: the original grant plus any take-back.

## B. Purchase actions

All three actions live in a new `services/admin_payments_service.py`. Each one locks the Purchase row `FOR UPDATE` (the same lock billing uses, so actions can't race a live capture or webhook), records `resolved_by_admin_id` / `resolved_at`, and has a router that commits.

**Re-check with PayPal** (`POST /admin/purchases/{id}/recheck`)

- Available for `pending`, `failed` **and `completed`** purchases. On completed ones it exists to spot refunds made in the PayPal dashboard when no webhook told us (always the case locally).
- Calls a new `billing_service.recheck_purchase()`, which asks the purchase's own gateway (`_gateway(purchase)`, so test purchases use the mock) for the order with `get_order`, then acts on the status:

| Order / capture status | Purchase was pending or failed | Purchase was completed |
|---|---|---|
| Order `COMPLETED`, capture `COMPLETED` | `_apply_capture(...)`: grants, if not already granted | no change |
| Capture `REFUNDED` / `PARTIALLY_REFUNDED` | marked `refunded`, no grant | marked `refunded` and `refunded_at` set; credits untouched (take-back is a separate action) |
| Order `APPROVED` | `_capture_and_fulfill()`: captures, then grants | n/a |
| `CREATED` / `PAYER_ACTION_REQUIRED` | stays pending: "buyer never approved" | n/a |
| `VOIDED`, or PayPal 404 `RESOURCE_NOT_FOUND` (expired order) | marked `failed`: "order expired / voided" | n/a |

- It never double-grants: the `purchase:{id}` ledger key plus the row lock guarantee that.
- Missing PayPal keys give a clear 503 ("PayPal not configured"); a timeout leaves everything unchanged and says so.
- Returns the outcome so the UI can show it.

**Take back credits** (`POST /admin/purchases/{id}/clawback`, with a required `note`)

- Only for `refunded` purchases.
- Removes `min(credits_granted, current balance)`, calculated under the wallet lock, so the balance can't go below zero.
- **If that amount is 0, nothing is written** and the response says nothing was taken back. The action stays available, so it can be retried after the user tops up. A zero-credit row would otherwise use up the once-only key for good.
- Otherwise uses `wallet_service.admin_adjust(-n, idempotency_key=f"refund_clawback:{purchase.id}")`, so it happens at most once per purchase.
- A partial take-back is final for this action. The panel shows "N of M credits taken back" and points to a manual adjustment for the rest.
- Sets the ledger row's `related_purchase_id` to the purchase and stores the note on the purchase.
- Writes no extra `manual_admin` Purchase row: the link to the refunded purchase *is* the audit record.
- Response: `{taken_back, requested, balance_after}`, so a partial take-back (the user had already spent the credits) is shown explicitly.

**Mark as failed** (`POST /admin/purchases/{id}/mark-failed`, with a required `note`)

- Only for `pending` purchases older than 24 hours (abandoned checkouts).
- **Runs Re-check first.** If PayPal shows the order as approved or paid, it is captured/credited instead and the request reports that. It is only marked failed when PayPal says it was never approved, voided or expired. An admin can't accidentally fail a purchase the buyer actually paid for.
- Moves no money.
- `failed` is still non-terminal, so if PayPal later reports a real completed payment, the credits are still granted. That is the correct outcome, since the money arrived.

**Data (one migration).** Add to `purchases`:

- `resolved_by_admin_id` (FK users, nullable)
- `resolved_at` (timestamptz)
- `refunded_at` (timestamptz). Set **wherever** a purchase becomes `refunded`: the REFUNDED/REVERSED webhook, `_apply_capture` when a capture comes back already refunded, and Re-check.

## C. Money on the detail pages

- **User detail:**
  - Add a **Purchases** section (reuse `billing_service.list_user_purchases`; test purchases are labelled).
  - Add `related_purchase_id` to `AdminCreditLedgerEntry`, so ledger rows link to their purchase and project.
- **Project detail:** add **Paid tiers**, a list of tier, credits charged and date. It comes from a new `wallet_service.download_charges_for_project(db, project_id)`, which reads the `download_spend` ledger rows using the existing `tier_from_download_key`.

## D. Overview

Four new tiles, from a new `admin_analytics_service.payment_stats(db, days)`. It touches only Purchase rows, so unlike `get_overview` it can be unit-tested on SQLite. Test purchases are excluded throughout.

| Tile | What it counts |
|---|---|
| Purchases (range) | completed purchases in the range |
| Pending purchases | all pending; links to `/admin/payments?status=pending` |
| Refunds (range) | by `refunded_at` |
| Paying users | distinct users with ≥1 completed PayPal purchase, all-time |

## E. Tiers & pricing page (new `/admin/tiers-pricing`)

**Tiers section.** Per tier: key (read-only, because it's used in storage paths), label, display order, on/off, download cost.

- New router `routers/admin/tiers.py`:
  - `GET /admin/tiers`
  - `PUT /admin/tiers/{key}` with `{label, sort_order, download_credit_cost}`
  - `PATCH /admin/tiers/{key}/active`
- New `tier_service.update_tier()`: label 1–64 chars, sort order is an integer, cost ≥ 1.
- The UI keeps the "below 3 credits" warning.

**Labels shown to users follow the DB.** Today the frontend's `tierLabel()` (`core/project-status.ts`, used in ~19 places) just capitalises the tier key and ignores `tiers.label`, so a rename would never reach users. Add a small `TierLabelService` (in `core/`), loaded once from the public `GET /tiers`, falling back to the capitalised key. Switch the project page, History badges, cost-gate copy and pricing grid to it.

**Credit packs section.** The existing pack editor moves here unchanged (its component is reused). `/admin/credit-packs` redirects to the new page.

**Model config** becomes AI models only: the per-tier model plus the vision model.

**Endpoint cleanup.** Remove `PUT /admin/model-config/tiers/{key}/download-cost` and `PATCH /admin/model-config/tiers/{key}/active`. Both now live under `/admin/tiers`, and only our own admin UI ever called them. Update the permission tests to match.

## F. Housekeeping

- **Admin nav order:** Overview, Users, Projects, **Payments**, Earnings, **Tiers & pricing**, Costs, Model config, Prompt templates, Cost gate. "Credit packs" leaves the nav.
- **Earnings:** remove the purchases table (now on Payments) and link to it instead.
- **Tests:**
  - `test_admin_payments_service.py`
    - Re-check: every row of the table above, for both pending and completed purchases; a completed purchase whose capture is now refunded becomes `refunded` with `refunded_at` and an unchanged balance; a 404 marks it failed; missing keys give a 503; a test purchase re-checks through the mock.
    - Take-back: refunded-only; once only; capped at the balance; **balance 0 writes nothing and can be retried later**.
    - Mark-failed: pending-only and older than 24 hours; refuses (and captures instead) when the order is approved or paid; a later completed webhook still grants.
    - `refunded_at` is set on every path that marks a purchase refunded.
  - `payment_stats`
  - `tier_service.update_tier` validation
  - `download_charges_for_project`
  - every new or moved route in `test_admin_router_permissions.py`
- **Docs:** PROGRESS.md (Milestone 8), CLAUDE.md admin bullet, `docs/paypal-payments-plan.md` (pointer to this plan).

## Build order

1. Migration, then `tier_service.update_tier`, `download_charges_for_project`, `payment_stats`, with tests.
2. `billing_service.recheck_purchase` (and setting `refunded_at` in the webhook handler), then `admin_payments_service`, with tests.
3. Routers:
   - payments status
   - the extended purchases list and detail
   - the three actions
   - tiers
   - additions to user/project detail and overview
   - endpoint cleanup
   - permission tests
4. Frontend:
   - Payments page (banner, table, detail panel, actions)
   - Tiers & pricing page
   - Model config trimmed
   - Overview tiles
   - User and project detail sections
   - nav, routes, redirect
5. Docs.

## Verification

1. `pytest` all green; `ng build` clean; `alembic upgrade head`.
2. **Manual, triggered by the user, in test mode** (`REDOWEBS_PAYMENTS_MODE=mock`):
   1. The banner says Test mode.
   2. Buy a pack. It shows on Payments only with "Show test purchases" on, and isn't counted on Overview or Earnings.
   3. **A real stuck purchase:** call `POST /api/v1/billing/paypal/orders` from Swagger (logged in) **without** capturing. It appears as `pending`. Click **Re-check**: it completes and the credits are added. A second click changes nothing (no second ledger row).
   4. Create another uncaptured order and back-date its `created_at` by more than 24 hours in the DB. **Mark as failed** runs Re-check first; the mock always reports test orders as paid, so this confirms the "refuses and credits instead" path. The "never approved" path needs the PayPal sandbox (step 3 below).
   5. Set a completed test purchase to `refunded` in the DB, then **Take back credits** twice: credits are removed once, and the second attempt returns the same result.
   6. On a user whose balance is 0, take-back reports 0 and stays available. Top them up, retry, and it removes the credits.
   7. **Tiers & pricing:** rename a tier and reorder it; the project page, History badge, pricing page and download button show the new label and order. Change a download cost; new downloads charge it, and tiers already bought stay free to re-download.
   8. User detail lists purchases; project detail lists paid tiers.
3. **With PayPal sandbox keys:** the banner says PayPal sandbox.
   1. Re-check an order that was approved but never captured: it captures and grants.
   2. Re-check an order that was never approved: it stays pending. Back-date it, and Mark as failed then succeeds.
   3. Refund a completed sandbox payment in the PayPal sandbox dashboard **with no webhook configured**, then Re-check it: it becomes `refunded` with the balance unchanged, and Take back credits becomes available.

## Review fixes (2026-10-05)

Found on re-reading the first draft against the code:

1. **Renames wouldn't reach users.** `tierLabel()` ignores `tiers.label`; added `TierLabelService` (section E).
2. **Take-back was unreachable without a webhook.** Re-check now also runs on completed purchases and detects refunds (section B).
3. **A 0-credit take-back burned the once-only key.** Now nothing is written for 0 (section B).
4. **Mark as failed could fail a paid purchase.** It now re-checks first (section B).
5. **Expired/404 orders and missing PayPal keys weren't handled** (section B).
6. **`refunded_at` was only set by the webhook.** It is now set on every refund path (section B, data).
7. **Verification didn't create a real stuck purchase.** It now uses an uncaptured order (Verification).
8. **`source=mock` with `include_mock=false` contradicted itself.** An explicit source wins (section A).
