# Pre-generation cost estimate + wallet-balance gate

Status: planned, not yet built. Written 2026-09-21.

## Context

The crawler can pull in up to 20 pages, but the AI generation step only ever
builds the home page, across up to 3 concurrently-enabled tiers, via an
agentic tool-calling loop (`site_generator.py`'s `_run_agent_loop`, OpenRouter,
up to `settings.generation_max_iterations = 24` round trips). If the home
page's content is unusually large, the `design.md` fed into that loop is
large, and the real OpenRouter cost across all enabled tiers can be
surprisingly high — while the user is only ever charged a flat
`wallet_service.GENERATION_SPEND_CREDITS = 1` credit per project regardless of
size (`tasks_generate.py:72-90`). Credit charges and real OpenRouter dollar
cost are already decoupled by design in this app (see CLAUDE.md's "3 free
signup credits" note), which is fine for typical pages but leaves the
platform operator exposed when a page is not typical.

Goal: right after crawling + blueprint-review finishes (before the expensive
generation step runs), estimate the total USD generation cost across all
enabled tiers. If it exceeds an admin-configurable threshold (default $1.00),
pause the pipeline, show the user a popup with the estimate, and require
their wallet balance to actually cover it (converted via an admin-configurable
USD-per-credit rate) before generation proceeds.

**Confirmed with the user, do not re-litigate without their sign-off:**
1. The gate requires real balance coverage, not just an acknowledge-and-continue popup.
2. The USD alert threshold is a new admin-editable setting (default $1.00), not a `config.py` constant.
3. The USD-per-credit conversion rate is also a new admin-editable setting — none exists anywhere in the codebase today.
4. No self-serve top-up exists yet (Stripe is fully unwired: only an unused `stripe_checkout_session_id` column and a reserved `source='stripe'` enum value). The user will wire a real payment gateway later and wants this kept in scope — meaning: don't build Stripe now, but design the insufficient-balance response/UI so wiring a real gateway later is a cheap swap-in, not a rework.

## How this fits the existing pipeline

- Chokepoint: `backend/app/workers/tasks_blueprint.py::extract_blueprint_task`. Today, once blueprint_review succeeds it unconditionally fans out one `generate_tier` job per enabled tier (lines 64-65). This is where the gate intercepts.
- `design.md` (`project_root/blueprint/design.md`) is the exact, fully-known, deterministic text fed into the agent loop as the user message (`site_generator.py:152-181`) — available at the chokepoint, before any tier's generation runs. It's the natural size signal to estimate from.
- Pricing infra already exists and must be reused, not reinvented: `token_usage_service.get_model_pricing(db)` / `estimate_cost_usd(...)`, backed by the admin-editable `ModelPricing` table with a seeded fallback dict. Historical `TokenUsageLog` rows (`purpose="generation"`) and `GenerationOutput.iterations`/`prompt_tokens`/`completion_tokens` are the self-calibration dataset.
- Concurrency: multiple `queue_worker.py` processes claim jobs via `SELECT ... FOR UPDATE SKIP LOCKED`. Since the gate works by simply *not enqueueing* `generate_tier` jobs until approved, nothing new needs locking — an unapproved project has nothing sitting in the queue.
- Frontend polling: `frontend/src/app/features/generation/generation-progress.component.ts` polls `GET /api/v1/projects/{id}` every 3s via `frontend/src/app/core/project-status.ts`'s `TERMINAL_STATUSES`/`BACKEND_STATUS_TO_STAGE`. This is already the single live poller — the new status just needs to not be added to `TERMINAL_STATUSES`, so polling continues through it.
- `/checkout` (`frontend/src/app/app.routes.ts`) already exists as a route, fully unwired (`CheckoutComponent.pay()` just navigates to `/history`). This is the reusable seam for "keep payment gateway in scope."

## Backend changes

### 1. New admin settings model — `backend/app/models/cost_setting.py`

Mirrors `AIModelSetting`'s key/value/upsert shape (not `ModelPricing`, which is a list of rows) but with a float value:

```python
class CostSetting(Base):
    __tablename__ = "cost_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
```

Two rows, keyed by code constants:
- `"generation_cost_alert_usd"` — default from new `Settings.generation_cost_alert_usd_default: float = 1.00` in `config.py`.
- `"usd_per_credit"` — default from new `Settings.usd_per_credit_default: float = 1.00`. No such rate exists anywhere today (the `pricing-tiers.ts` $19/$39/$79 figures are unwired marketing placeholders, not tied to `Tier.download_credit_cost`); $1.00 is a clean placeholder, explicitly admin-tunable from day one so the exact number doesn't block shipping.

Register in `backend/app/models/__init__.py`.

### 2. `backend/app/services/cost_settings_service.py` (new)

Same shape as `model_config_service.get_vision_model`/`set_vision_model` — row present wins, row absent falls back to the `config.py` default:

```python
def get_generation_cost_alert_usd(db=None) -> float
def set_generation_cost_alert_usd(value: float, admin_id, db=None) -> CostSetting
def get_usd_per_credit(db=None) -> float
def set_usd_per_credit(value: float, admin_id, db=None) -> CostSetting
```

### 3. `backend/app/services/cost_estimation_service.py` (new)

**No `tiktoken` dependency.** The real generation models are OpenRouter-routed (`deepseek/deepseek-v4.1-flash` default, per-tier overrides), not OpenAI's own tokenizer family — `tiktoken` would give false precision. Instead, use a **calibrated chars-per-token heuristic that self-corrects from this project's own historical data**, per model:

```python
DEFAULT_CHARS_PER_TOKEN = 4.0        # cold-start fallback
DEFAULT_ESTIMATED_ITERATIONS = 3     # cold-start fallback
DEFAULT_COMPLETION_TOKENS = 6000     # cold-start fallback
MIN_CALIBRATION_SAMPLES = 3          # below this, treat as cold start

@dataclass
class TierCostEstimate:
    tier_key: str
    model_name: str
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_cost_usd: float
    calibrated: bool

@dataclass
class GenerationCostEstimate:
    total_estimated_cost_usd: float
    per_tier: list[TierCostEstimate]

def estimate_generation_cost(db, tier_keys: list[str], design_md: str) -> GenerationCostEstimate
def build_cost_gate_info(db, project, wallet_balance: int, usd_per_credit: float) -> "GenerationCostGateInfo"
```

Estimation math (deterministic given inputs → unit-testable without a DB):
- `chars_per_token` = historical average of `TokenUsageLog.prompt_tokens / design_md_char_count` for that `model_name` (join `TokenUsageLog.job_id → GenerationJob.blueprint_id → Blueprint.design_md_storage_path`, read each past `design.md`'s char count off disk, skip rows whose file no longer exists), when ≥`MIN_CALIBRATION_SAMPLES` usable rows exist; else `DEFAULT_CHARS_PER_TOKEN`.
- `estimated_iterations` = historical average of `GenerationOutput.iterations` for that model/tier when calibrated, else `DEFAULT_ESTIMATED_ITERATIONS` — always capped at `settings.generation_max_iterations` regardless of calibration.
- `estimated_prompt_tokens = round(len(design_md) / chars_per_token) * estimated_iterations` — deliberately linear/conservative: real runs benefit from `settings.generation_prompt_caching_enabled` cutting repeated-prefix cost, so this errs toward **over**-estimating, the safer direction for a spend gate. Document this bias in the module docstring.
- `estimated_completion_tokens` = historical average of `GenerationOutput.completion_tokens` when calibrated, else `DEFAULT_COMPLETION_TOKENS`.
- Cost per tier = `token_usage_service.estimate_cost_usd(model_name, estimated_prompt_tokens, estimated_completion_tokens, token_usage_service.get_model_pricing(db))` — reuse existing pricing, don't reinvent it.
- Resolve each tier's model via `model_config_service.get_generation_model(tier_key, db)`; sum across `tier_keys` (two tiers on the same model still both count — each runs its own full agent loop).

`build_cost_gate_info` does **not** recompute the estimate — it reads the already-persisted `project.estimated_generation_cost_usd` (see §5), converts it to `required_credits = math.ceil(estimated_cost_usd / usd_per_credit)`, and computes `shortfall_credits = max(0, required_credits - wallet_balance)`. This single function is the only place that math exists — both the approval endpoint (§6) and the status-poll endpoint (§7) call it rather than each inlining their own copy.

### 4. Edit `tasks_blueprint.py::extract_blueprint_task`

Extract the enqueue loop into a shared helper (so the new approval endpoint can reuse it without duplicating logic), and gate it:

```python
def enqueue_tier_jobs(db, project_id: str, tier_keys: list[str]) -> None:
    for tier_key in tier_keys:
        enqueue(db, "generate_tier", {"project_id": project_id, "tier": tier_key})

# replacing the current unconditional loop:
design_md = (project_root / "blueprint" / "design.md").read_text(encoding="utf-8")
estimate = cost_estimation_service.estimate_generation_cost(db, tier_keys, design_md)
alert_threshold_usd = cost_settings_service.get_generation_cost_alert_usd(db)

if estimate.total_estimated_cost_usd > alert_threshold_usd:
    project.status = "awaiting_cost_approval"
    project.estimated_generation_cost_usd = estimate.total_estimated_cost_usd
    project.pending_tier_keys = tier_keys
else:
    enqueue_tier_jobs(db, project_id, tier_keys)
```

Under-threshold path is byte-for-byte today's behavior — zero regression for the common case. The popup is shown **whenever the threshold is exceeded, regardless of current balance** (matches "estimate the cost ... show a popup" as always-show-for-awareness); the modal itself branches into a one-click Continue (balance sufficient) or a blocked Top Up state (balance insufficient) — both go through the same approval endpoint.

### 5. New `Project` columns

```python
estimated_generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
pending_tier_keys: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

`pending_tier_keys` snapshots the enabled tiers *at gate time*, so approval enqueues exactly what was quoted even if an admin disables a tier while the project waits. `usd_per_credit` is **not** snapshotted — it's re-read live at both poll time and approval time, so an admin rate change applies immediately to any pending project.

### 6. New endpoint — `POST /api/v1/projects/{project_id}/approve-generation`

In `backend/app/routers/projects.py`, same ownership-check pattern as the existing `get_project_status`:

```python
@router.post("/projects/{project_id}/approve-generation", response_model=GenerationApprovalResponse)
def approve_generation(project_id, db=Depends(get_db), current_user=Depends(get_current_user)):
    project = ...  # load + 404 if not owned, same as get_project_status
    if project.status != "awaiting_cost_approval":
        raise HTTPException(409, "No pending generation approval for this project")

    wallet = wallet_service.get_or_create_wallet(db, current_user.id)
    usd_per_credit = cost_settings_service.get_usd_per_credit(db)
    gate_info = cost_estimation_service.build_cost_gate_info(db, project, wallet.balance, usd_per_credit)

    if gate_info.shortfall_credits > 0:
        return GenerationApprovalResponse(approved=False, status="awaiting_cost_approval", **gate_info.model_dump())

    enqueue_tier_jobs(db, project_id, project.pending_tier_keys)
    project.status = "blueprint_ready"
    project.pending_tier_keys = None
    db.commit()
    return GenerationApprovalResponse(approved=True, status="blueprint_ready", **gate_info.model_dump())
```

200 OK with `approved: false` on insufficient balance (not a 402/error) — a normal, poll-able outcome, not a fault. **No debit happens here.** The existing flat `wallet_service.spend()` inside `generate_tier_task` (`tasks_generate.py:73-90`) remains the sole, authoritative, row-locked charge, unchanged — this endpoint is purely a balance-sufficiency pre-check against the *estimate*. This is an explicit scope decision: the flat 1-credit generation charge is not being replaced by a variable one in this change; confirm this reading is right before/while building.

New schema in `backend/app/schemas/project.py`:
```python
class GenerationApprovalResponse(BaseModel):
    project_id: str
    status: str
    approved: bool
    estimated_cost_usd: float
    required_credits: int
    current_balance: int
    shortfall_credits: int
```

### 7. `ProjectStatusResponse` gains a `cost_gate` field

```python
class GenerationCostGateInfo(BaseModel):
    estimated_cost_usd: float
    required_credits: int
    current_balance: int
    shortfall_credits: int

class ProjectStatusResponse(BaseModel):
    ...  # unchanged existing fields
    cost_gate: GenerationCostGateInfo | None = None
```

`get_project_status` populates `cost_gate` only when `status == "awaiting_cost_approval"`, calling the same `cost_estimation_service.build_cost_gate_info(...)` helper as the approval endpoint (§6) — the `ceil()`/shortfall math lives in exactly one place.

### 8. Admin settings CRUD — `backend/app/routers/admin/cost_gate_config.py` (new)

Mirrors `routers/admin/model_config.py`'s vision-model GET/PUT shape exactly:
```
GET/PUT /api/v1/admin/cost-gate/threshold
GET/PUT /api/v1/admin/cost-gate/usd-per-credit
```
New schemas `backend/app/schemas/admin/cost_gate_config.py` (mirrors `schemas/admin/model_config.py` field-for-field, `model_name: str` → `value_usd: float`). Register in `backend/app/routers/admin/__init__.py` alongside the other admin sub-routers — inherits `require_admin` from the parent router automatically.

## Frontend changes

- `frontend/src/app/core/project-status.ts`: add `'awaiting_approval'` to `Stage`, map `BACKEND_STATUS_TO_STAGE['awaiting_cost_approval']`, add a status label. **Do not** add it to `TERMINAL_STATUSES` — polling must continue so the modal can react once the user acts.
- `frontend/src/app/features/generation/generation-progress.component.ts`: polling already continues unchanged (`takeWhile` keys off `TERMINAL_STATUSES`). In its status handler, when `status === 'awaiting_cost_approval'`, set a `costGate` signal from `res.cost_gate` and render the modal instead of progressing the normal stage UI.
- New `frontend/src/app/features/generation/cost-gate-modal/cost-gate-modal.component.ts` (+`.html`/`.css`): presentational, `@Input() costGate`, `(approve)` output. Calls new `RedoWebsApiService.approveGeneration(projectId)` → `POST /projects/{id}/approve-generation`. On `approved: false`, re-render with the fresh shortfall plus a **Top Up** button; on `approved: true`, do nothing extra — the next poll tick naturally observes the status flip and the modal unmounts.
- **Payment-gateway seam**: the Top Up button routes to the existing `/checkout` route with a `credits` query param (`router.navigate(['/checkout'], { queryParams: { credits: shortfallCredits } })`), matching how `CheckoutComponent` already reads a `tier` query param. No payment logic is built now — `CheckoutComponent.pay()` keeps its current no-op-to-`/history` behavior — but the value a real gateway integration needs is already threaded through.
- `frontend/src/app/core/redowebs-api.models.ts` / `redowebs-api.service.ts`: add `GenerationCostGateInfo`, `GenerationApprovalResponse`, `cost_gate?` on `ProjectStatusResponse`, `approveGeneration()`.
- Admin settings screen: new `frontend/src/app/features/admin/cost-gate/admin-cost-gate.component.ts` (+`.html`), mirroring `admin-model-config.component.ts`'s draft-signal/save/reload pattern — two number inputs (alert threshold USD, USD-per-credit) with Save buttons. Wire into `admin-api.service.ts`, `admin-api.models.ts`, `admin.routes.ts` (new lazy `cost-gate` route), and the nav in `admin-shell.component.ts`.

## Migration (Alembic)

Current head, confirmed by walking `alembic/versions/`: `5d005e06ba56` (`5d005e06ba56_add_prompt_templates.py`). New revision's `down_revision = '5d005e06ba56'`:
- `op.create_table('cost_settings', key String(64) PK, value Float NOT NULL, updated_at, updated_by_admin_id FK users.id)`.
- `op.add_column('projects', sa.Column('estimated_generation_cost_usd', sa.Float(), nullable=True))`.
- `op.add_column('projects', sa.Column('pending_tier_keys', postgresql.JSONB(), nullable=True))`.
- No backfill needed (all nullable, existing rows unaffected). `downgrade()` drops the two `projects` columns and the `cost_settings` table.

## Tests (deterministic pieces only, per this project's testing bar)

- `backend/tests/test_cost_estimation_service.py` — chars→tokens math with fixed inputs; `estimate_generation_cost` given a fixed `design_md` length + fake calibration ratios + a fixed pricing dict → exact expected USD; cold-start path (no `TokenUsageLog` history) falls back to the documented constants rather than crashing or returning 0; `build_cost_gate_info`'s shortfall math (sufficient/insufficient/exact-boundary balance). Do not test whether the estimate is realistic — that's the same "don't test AI output quality" boundary this project already draws elsewhere.
- `backend/tests/test_cost_settings_service.py` — mirrors `test_model_config_service.py`'s style: row-absent → config default; row-present → DB value wins; `set_*` upserts rather than duplicating.
- `backend/tests/test_tasks_blueprint_cost_gate.py` — monkeypatch the estimator; under-threshold path enqueues every `tier_key` exactly as before (regression check) with status untouched by the gate; over-threshold path enqueues nothing, sets `status = "awaiting_cost_approval"`, and persists `estimated_generation_cost_usd`/`pending_tier_keys`.
- `backend/tests/test_projects_approve_generation.py` — balance-sufficient path enqueues + flips status; balance-insufficient path returns `approved=False` with correct `shortfall_credits` and does not enqueue; a second call after approval 409s rather than double-enqueueing.

## Known gaps / explicit follow-ups (not built now)

1. **Charging stays flat.** This change only gates/blocks; it doesn't make the actual generation charge variable. `required_credits` is a pre-flight sufficiency check against the *estimate*, disconnected from `Tier.download_credit_cost` economics.
2. **No expiry job** for a project stuck in `awaiting_cost_approval` if the user never returns — reasonable today since there's no self-serve top-up to make "waiting" resolvable anyway; a scheduled sweep is a future follow-up.
3. **`generate_full_site_task`** (the lazy multi-page path triggered on first paid download) is **not** gated by this change — different cost profile, own existing `download_spend` charge. Flagged as a natural future extension of the same estimator, out of scope now.
4. **No wallet locking at gate-check time** (`get_or_create_wallet` is a plain read) — fine, since the authoritative locked charge still happens later in `generate_tier_task`'s existing `wallet_service.spend()`. This gate can only ever be *stricter* than necessary in a benign race, never leak free generation.

## Verification

1. `alembic upgrade head` applies cleanly; `alembic downgrade -1` reverses cleanly.
2. Run the new backend unit tests (`pytest backend/tests/test_cost_estimation_service.py backend/tests/test_cost_settings_service.py backend/tests/test_tasks_blueprint_cost_gate.py backend/tests/test_projects_approve_generation.py`) plus the full existing suite to confirm no regression in the under-threshold path.
3. Manual/exploratory (per this project's "don't over-invest in e2e for subjective AI output" philosophy, but this gate's plumbing is worth a real click-through): set `generation_cost_alert_usd` to a very low value via the new admin screen, submit a real small site, confirm the popup appears mid-pipeline, confirm Continue with sufficient balance actually resumes generation, and confirm insufficient balance shows the blocked state with correct shortfall math and a working Top Up link into `/checkout`.
4. Once built, update `docs/PROGRESS.md` per this project's working-style convention of keeping build status resumable across sessions.
