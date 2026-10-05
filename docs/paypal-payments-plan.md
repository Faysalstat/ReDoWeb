> **Admin follow-up:** purchase operations (Payments page, Re-check / Take back credits / Mark as failed, Tiers & pricing) are designed in `docs/admin-payments-plan.md`.
>
> **Status (2026-10-05): implemented.** Backend, frontend and tests are built per this plan; not yet run against a real PayPal sandbox (waiting on sandbox credentials) or a live Postgres (`alembic upgrade head` for migration `b7d3f1a8c2e6` still to run). See docs/PROGRESS.md. Two refinements made during implementation: a `failed` purchase is not terminal (a later valid COMPLETED capture still grants, since PayPal lets a buyer retry a declined order with another card), and Pay Later/Venmo are disabled so the buttons offer only PayPal + card.

# Plan: PayPal credit-pack payments + admin-configurable packs and download costs

## Context

Milestone 7 (billing) was planned around Stripe, but nothing Stripe-specific was ever built. Only an unused `purchases.stripe_checkout_session_id` column and a reserved `source="stripe"` value exist. The user has chosen **PayPal** instead (approved 2026-10-05). Their decisions:

- **Credit packs:** admin-configurable in the admin panel, each pack carrying **its own price** so larger packs can be discounted. Prices are not derived from `usd_per_credit`.
- **Download costs:** the per-tier download credit cost (`tiers.download_credit_cost`) must be **editable from the admin panel**. Today it can only change through a migration seed.
- **Cards:** users can **pay by card** as well as with a PayPal account.
- **PayPal sandbox:** the user will arrange sandbox credentials. The design must therefore work locally with only a client ID and secret, and not depend on webhooks for the happy path.

**Goal:** a user who is short on credits (at a download or at the cost gate) can buy a pack through PayPal. Credits land in the ledger exactly once, and the user returns to what they were doing. The download zip should also be cleaned up so it no longer ships internal debug files.

## Payment flow

The design uses the PayPal Orders v2 API and the JS SDK Smart Buttons. Credits are granted at server-side capture, and a webhook acts as a safety net.

1. The frontend loads the PayPal JS SDK using the client ID from `GET /billing/config`, with `enable-funding=card` so the "Debit or Credit Card" button shows.
2. `createOrder` calls `POST /billing/paypal/orders {pack_id}`. The backend:
   - creates `Purchase(status="pending")`, snapshotting the pack's credits and price;
   - creates the PayPal order with `custom_id = purchase.id` and the price taken from the server-side snapshot (never the client);
   - stores `paypal_order_id` and returns it.
3. `onApprove` calls `POST /billing/paypal/orders/{id}/capture`. The backend checks ownership (404 if the order isn't the caller's), then runs the shared internal `_capture_and_fulfill(db, purchase)`:
   1. lock the Purchase row (`FOR UPDATE`);
   2. return early if the purchase is already completed;
   3. call PayPal capture;
   4. check the capture status is `COMPLETED` and that the amount and currency match the snapshot;
   5. grant the credits.
4. `POST /billing/paypal/webhook` handles the case where the user closed the tab after approving. The backend verifies the event using PayPal's `verify-webhook-signature` API, passing the parsed event body unmodified, then:
   - on `CHECKOUT.ORDER.APPROVED`, calls the same `_capture_and_fulfill`. The webhook has no logged-in user, so it looks the purchase up by `paypal_order_id` / `custom_id` with **no ownership check**. Ownership is only a concern for the user-facing endpoint.
   - on `PAYMENT.CAPTURE.COMPLETED`, fulfils the purchase. The order ID is at `resource.supplementary_data.related_ids.order_id`, with `resource.custom_id` (the purchase ID) as a fallback.
   - on `PAYMENT.CAPTURE.DENIED` / `REFUNDED`, only marks the status. Refunds are not clawed back automatically (per the PRD); an admin uses the existing manual adjustment.

**Exactly-once crediting** rests on two guards: the Purchase row lock serializes capture against the webhook, and the ledger idempotency key `purchase:{purchase.id}` guarantees a single credit even if both paths run.

**Edge cases**

- **Racing captures (expected on nearly every purchase).** `CHECKOUT.ORDER.APPROVED` fires for almost every order, so the browser's capture and the webhook's capture will routinely race. Whichever runs second either sees the purchase already `completed` under the lock, or gets PayPal's `422 ORDER_ALREADY_CAPTURED`. The latter is **not an error**: fetch the order with `GET /v2/checkout/orders/{id}` and fulfil from its existing capture.
- **PayPal call timeout.** The row lock is held during the PayPal HTTP call. That's acceptable because each lock covers a single purchase, but the call uses a bounded `httpx` timeout. A timeout or network error leaves the purchase **pending**, not failed. A retry is safe because of the same `PayPal-Request-Id`, and the webhook completes it otherwise.
- **`PENDING` capture** (for example an eCheck, or a receiving-preference hold): the purchase stays pending and the webhook completes it later.
- **Abandoned orders** (approval never happens) stay `pending` forever. This is harmless: revenue only counts `completed`, and the admin purchases list shows them. No cleanup job in v1.
- **`usd_per_credit` is not a price.** It stays only as the cost gate's dollar-estimate-to-credits conversion (`cost_estimation_service`). Pack prices are independent of it. Say so in its admin-page description so it isn't mistaken for pack pricing.

## Backend changes

### Data (one migration, off head `a1e5c9d34f7b`)

- **New `credit_packs` table:** `id` UUID, `name`, `credits` int, `price_usd_cents` int, `is_active`, `sort_order`, `created_at`, `updated_at`, `updated_by_admin_id`.
  - Packs are disabled, never hard-deleted, so purchase history stays meaningful.
  - Seed two placeholder packs as **inactive**. Admins set real values.
- **`purchases` changes:**
  - rename `stripe_checkout_session_id` to `paypal_order_id` (still unique). Also rename its Postgres unique constraint (`purchases_stripe_checkout_session_id_key`) so no Stripe-named object is left behind. `downgrade()` reverses both renames;
  - add `paypal_capture_id` (unique, nullable);
  - add `credit_pack_id` (FK, nullable; manual admin rows have none);
  - `status` gains `pending`, `failed`, `refunded`;
  - `source` gains `"paypal"`.
- The new model goes in `backend/app/models/credit_pack.py`, registered in `models/__init__.py`. Update `models/purchase.py` and the stale `reason` docstring in `models/wallet.py`.
- Add `CreditPack` to the SQLite table list in `backend/tests/conftest.py`. It has no FK to `projects`, so SQLite is fine.

### Config (`backend/app/config.py`, `REDOWEBS_` prefix, same style as `openrouter_api_key`)

- `paypal_client_id`
- `paypal_client_secret`
- `paypal_env` (`sandbox` | `live`, which maps to the API base URL)
- `paypal_webhook_id`
- `paypal_brand_name`

Document all of these in `docs/INSTALLATION.md` and `docs/RAILWAY.md`.

### PayPal client: `backend/app/payments/paypal_client.py`

- Uses `httpx` directly, like `ai/openrouter_client.py` (no PayPal SDK).
- Functions:
  - `get_access_token()`: client-credentials grant, cached until shortly before expiry;
  - `create_order(purchase_id, amount_cents, description)`;
  - `capture_order(order_id)`;
  - `verify_webhook_signature(headers, raw_body)`.
- Sends a `PayPal-Request-Id` header on create and capture, so a retried call is idempotent on PayPal's side too.
- Raises one `PayPalError` on any failure.

### Services

- **`wallet_service.grant_purchase_credits(db, user_id, amount, *, purchase_id, idempotency_key)`**
  - Same lock-then-idempotency-check ordering as `spend()` (not the check-then-lock order `admin_adjust` uses).
  - Writes `reason="purchase"` and `related_purchase_id`. The caller commits.
- **New `services/billing_service.py`**
  - `list_active_packs()`
  - `create_order(db, user, pack_id)`
  - `capture_order(db, user, order_id)`
  - `fulfill_purchase(db, purchase, capture)`: shared by capture and webhook. It validates the amount and currency, sets the capture ID, and calls `grant_purchase_credits` with key `purchase:{id}`.
  - `handle_webhook_event(db, event)`
  - Small pure helpers for testability, e.g. `_validate_capture(capture, purchase)` returning ok or a reason. This mirrors the extract-for-testability style of `_resolve_download_plan`.
- **New `services/credit_pack_service.py`:** admin CRUD (create/update/set_active) with validation that credits ≥ 1 and price > 0.
  - There is no arbitrary minimum price.
  - The admin UI warns when a pack is small enough that PayPal's fixed per-transaction fee (about $0.49 + ~3.5%) eats most of it.
- **`tier_service.set_download_cost(key, cost, admin_id, db=None)`**
  - Same shape as `set_generation_model` / `set_active`.
  - Cost must be ≥ 1.
  - The admin UI warns when the cost is below 3, which would break the "free signup credits can't buy a download" intent. This is a warning, not a block.

### Routers

**New `routers/billing.py`:**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/billing/config` | public | Returns the client ID, currency and env. The client ID is public by design, so the frontend needs no build-time PayPal config. |
| GET | `/api/v1/billing/credit-packs` | **public** | Active packs only. `/pricing` and the home page's pricing section are public routes, so this can't require login. |
| POST | `/api/v1/billing/paypal/orders` | JWT | Rate-limited with slowapi, like `POST /projects`, to stop pending-row spam. |
| POST | `/api/v1/billing/paypal/orders/{order_id}/capture` | JWT | Returns `{status: completed\|pending\|failed, credits_granted, balance}`. |
| GET | `/api/v1/billing/purchases` | JWT | The current user's own purchase history. |
| POST | `/api/v1/billing/paypal/webhook` | signature | No JWT. Verified signature or 400, and nothing is granted on a bad signature. |

**New public `GET /api/v1/tiers`:** active tiers with label and `download_credit_cost`, with no auth, for the same reason as the packs endpoint. The pricing page and download buttons use it to show real costs.

**Admin:**

- New `routers/admin/credit_packs.py`: `GET` / `POST /admin/credit-packs`, `PUT /admin/credit-packs/{id}`, `PATCH /admin/credit-packs/{id}/active`. Copy the `routers/admin/costs.py` model-pricing pattern and wire it in `routers/admin/__init__.py`.
- Add `PUT /admin/model-config/tiers/{key}/download-cost` to `routers/admin/model_config.py`, and add `download_credit_cost` to `AdminTierModelRow`.
- New `GET /admin/purchases` (paged, filterable by status and source) to cover the PRD's FR13 "payments" item.
- Earnings: rename `stripe_revenue_usd_in_range` to `paypal_revenue_usd_in_range` in `admin_analytics_service.revenue_breakdown` and `schemas/admin/earnings.py`. `_sum_cents` already filters `status=="completed"`, so pending and failed purchases never count as revenue.
- Add every new admin route to `ADMIN_ROUTES` in `tests/test_admin_router_permissions.py`.

`main.py`: include `billing.router` and the tiers router. The CORS setup is unchanged.

### Downloads

**Already built (2026-09-17), kept as-is:**

- `routers/downloads.py` (start / status / file).
- One charge per (project, tier), with free re-downloads.
- The lazy full-site build for multi-page sites (`workers/tasks_full_site.py`).
- The download button in `generation-progress`.

**Changes in this plan:**

- **Zip cleanup** (`services/download_service.py`): exclude `_debug_trace*.json` and `blueprint.json`, using `zipfile` with a skip filter instead of `shutil.make_archive`. Keep `design.md`, `images/` and `sitemap.xml`, as FR9 requires.
- **Structured 402** (`routers/downloads.py`): `{required, balance, shortfall}`, so the frontend can offer an exact top-up.
- **Paid-tier indicator:**
  - Add `purchased_tiers: list[str]` to `ProjectStatusResponse` (`routers/projects.py`, `schemas/project.py`).
  - Derive it from existing `download_spend` ledger rows, matching on idempotency key prefix `download_spend:{project_id}:`. This needs no new table.
  - Also add the field to the `GET /projects` list items, for History.
- **History page** (`features/history/`): a "Purchased" badge plus a Download action per paid tier, linking to the project page's download (FR15 re-download). Unpaid tiers link to the project as today.

## Frontend changes

- **New `core/wallet.service.ts`:** a shared `balance` signal with `refresh()`.
  - `shared/ui/app-header/app-header.component.ts` and `features/home/home.component.ts` switch to it, so the header updates right after a purchase. Today the balance only refreshes when auth state changes.
- **New `core/paypal-sdk.loader.ts`:** injects the SDK `<script>` once, using the client ID from `/billing/config`, `currency=USD`, `intent=capture` and `enable-funding=card`.
- **`features/checkout/` rewrite**, replacing the mock card form:
  1. Pack selector, preselecting the smallest pack ≥ `?credits=`.
  2. PayPal Smart Buttons; `createOrder` and `onApprove` call the backend.
  3. Four outcome states: success, **pending** ("payment received, credits will appear shortly"), error, and cancel.
  4. An empty state when no pack is active, since the seeded packs start inactive.
  5. Refresh the wallet, then navigate back to `?returnUrl=`. Only same-app paths are accepted (must start with `/` and not `//`); anything else falls back to `/history`, to prevent an open redirect.
  6. Add `authGuard` to the `/checkout` route.
- **Remove the dummy prices file.** `core/pricing-tiers.ts` ($19/$39/$79) is imported by **three** places: `features/pricing/`, `features/home/home.component.ts` (embedded pricing section) and `features/checkout/`. All three switch to real packs and tier download costs from the public API, then the file is deleted.
- **`features/billing-settings/`:** show purchase history from `/billing/purchases`.
- **`features/generation/generation-progress.component.ts`:**
  - Show each tier's credit cost on its download button, or "Purchased · re-download free" when the tier is in `purchased_tiers`.
  - Refresh the shared wallet balance after a successful download charge.
  - On a 402, show "Needs N credits, you have M" with a Top Up button that goes to `/checkout?credits=<shortfall>&returnUrl=/projects/<id>`.
  - Retry the download on return.
  - Give the existing cost-gate Top Up a `returnUrl` too.
- **Admin:**
  - New `features/admin/credit-packs/` page (list, create, edit, enable/disable), with a route in `admin.routes.ts` and a link in `admin-shell.component.ts`.
  - A download-cost input on `admin-model-config` tier rows.
  - A recent-purchases table on the earnings page, and the label renamed to PayPal.
  - `admin-api.service.ts` / `admin-api.models.ts` extended to match.
- `app.routes.ts`: update the "unwired shell" comments. `/checkout` and `/settings/billing` become real and auth-guarded.

## Docs

- `CLAUDE.md`: add a settled-decision bullet "Payments are PayPal, not Stripe (user decision 2026-10-05)" covering the order/capture/webhook design. Fix the existing Stripe mentions.
- `docs/PRD.md` (FR8 and the scope bullets) and `docs/implementation-plan.md` (stack, schema, API, Milestone 7): replace Stripe with PayPal.
- `docs/PROGRESS.md`: update Milestones 5 and 7.
- Save this plan as `docs/paypal-payments-plan.md`.

## Build order

1. Migration, models, `grant_purchase_credits` and `tier_service.set_download_cost`, with tests.
2. `paypal_client` and `billing_service`, with tests using mocked HTTP.
3. Routers (billing, tiers, admin packs, purchases, download cost, earnings rename), plus the permission smoke tests.
4. Downloads: zip filter, structured 402, and `purchased_tiers` on project status and list.
5. Frontend: wallet service and SDK loader, then checkout, then the generation-progress 402 path, then the pricing and billing pages, then the admin pages.
6. Docs.

## Tests (per the CLAUDE.md testing bar: wallet math, pricing, webhook, permissions)

**`test_wallet_service.py`**

- `grant_purchase_credits` credits once.
- The same key a second time is a no-op.
- The lock comes before the idempotency check.

**`test_billing_service.py`** (PayPal client monkeypatched)

- `create_order` snapshots the pack price; a later price change doesn't affect an open order.
- Capture gets `422 ORDER_ALREADY_CAPTURED`: it fetches the order and fulfils once, without failing.
- A capture timeout leaves the purchase pending (not failed) with no grant.
- A webhook `CHECKOUT.ORDER.APPROVED` captures without any user context.
- An inactive or unknown pack is rejected.
- Capturing another user's order returns 404.
- A completed capture grants once; capturing twice doesn't double-grant.
- An amount or currency mismatch grants nothing and marks the purchase failed.
- A `PENDING` capture leaves the purchase pending.
- Capture followed by the webhook for the same order grants once.
- A webhook for an unknown order is ignored.
- A refund webhook marks the purchase refunded without changing the balance.

**`test_paypal_client.py`** (`monkeypatch httpx.post`, same style as `test_openrouter_client.py`)

- Token caching and refresh.
- Request bodies and the `PayPal-Request-Id` header.
- Verify-signature success and failure.

**`test_billing_webhook.py`**

- An invalid signature gets 400 and no ledger row.

**`test_credit_pack_service.py`, `test_tier_service.py`**

- Validation, set-active, and download-cost bounds.

**`test_download_service.py`, `test_downloads_plan.py`**

- The zip excludes debug traces and keeps `design.md`, `images/` and `sitemap.xml`.
- `_resolve_download_plan` cases. These were flagged as missing in PROGRESS.md.

## PayPal account prerequisites (user, before the sandbox test)

- Confirm the business account's country can **receive** PayPal payments. Some countries can only send.
- In the business account's website payment settings, turn on **"PayPal account optional"**. Without it, the card / guest-checkout button won't appear.
- Make **USD** an accepted currency without manual review. Otherwise captures can return `PENDING` (`RECEIVING_PREFERENCE_MANDATES_MANUAL_ACTION`) until accepted by hand.
- Create a sandbox REST app (client ID + secret) and a sandbox personal buyer account.

## Verification

1. `pytest` from `backend/` (all green), and `ng build` clean.
2. `alembic upgrade head` against the local Postgres.
3. **Manual sandbox run, triggered by the user**, after setting `REDOWEBS_PAYPAL_CLIENT_ID`, `REDOWEBS_PAYPAL_CLIENT_SECRET` and `REDOWEBS_PAYPAL_ENV=sandbox`:
   1. Create and activate a pack in the admin panel, and set the `pro` download cost.
   2. With too few credits, click Download. Check that the 402 prompt appears and the Top Up link carries the shortfall.
   3. Pay with the sandbox buyer account. Check the balance updates in the header, a `purchase` ledger row exists, and the purchase is `completed` with a capture ID.
   4. Return to the project and confirm the download succeeds.
   5. Repeat using the card button with a PayPal sandbox test card.
   6. Re-POST the capture for the same order and confirm no second credit.
4. **Downloads, first live end-to-end test:**
   1. Download a paid tier of a single-page project. Unzip it and confirm `design.md`, the HTML/CSS, `images/` and `sitemap.xml` are present and no `_debug_trace*` files.
   2. Download again: there's no second ledger row and the button shows "Purchased".
   3. Download a tier of a multi-page project (6+ pages). The full-site build runs, one HTML file per page is produced, and `index.html` is untouched.
   4. History shows the Purchased badge.
5. **Webhook (optional locally):** register the webhook in the sandbox app against an ngrok URL or the Railway deployment, set `REDOWEBS_PAYPAL_WEBHOOK_ID`, and use the PayPal webhook simulator. Then approve a payment, close the tab before capture, and confirm the webhook path grants the credits.
6. Check the admin earnings page: PayPal revenue counts only completed purchases.
