from datetime import datetime

from pydantic import BaseModel


class ProjectSubmitResponse(BaseModel):
    project_id: str
    status: str


class ProjectListItem(BaseModel):
    project_id: str
    source_url: str
    status: str
    created_at: datetime
    tier: str | None = None
    # Tiers the user has already paid to download (free re-download).
    purchased_tiers: list[str] = []


class ProjectBlueprintSummary(BaseModel):
    site_name: str | None = None
    colors: dict | None = None
    fonts: dict | None = None
    tone: str | None = None


class ProjectGenerationSummary(BaseModel):
    tier: str
    template_used: str
    preview_url_path: str
    summary: str | None = None
    contrast_warnings: list[str] = []


class ProjectTierFailure(BaseModel):
    """One enabled tier whose latest preview generation failed. Reported
    alongside (not instead of) whatever other tiers succeeded -- a single
    tier failing never fails the whole project. Retry it with
    POST /projects/{id}/retry-tier?tier=..., which costs no extra credits."""

    tier: str
    failure_reason: str | None = None


class TierRetryResponse(BaseModel):
    project_id: str
    tier: str
    status: str


class GenerationCostGateInfo(BaseModel):
    """Populated on ProjectStatusResponse only while status ==
    "awaiting_cost_approval" -- see docs/generation-cost-gate-plan.md."""

    estimated_cost_usd: float
    required_credits: int
    current_balance: int
    shortfall_credits: int


class GenerationApprovalResponse(BaseModel):
    project_id: str
    status: str
    approved: bool
    estimated_cost_usd: float
    required_credits: int
    current_balance: int
    shortfall_credits: int


class ProjectTierActions(BaseModel):
    """Post-purchase action state for one tier (see
    services/tier_actions_service.py) -- drives the Generate all pages /
    Run SEO buttons on load and while polling. Each status is
    none | running | succeeded | failed."""

    full_site_status: str = "none"
    full_site_failure_reason: str | None = None
    seo_available: bool = False
    seo_status: str = "none"
    seo_failure_reason: str | None = None
    # Live SEO run progress (latest SEO job): status, step, label, percent,
    # detail, the step checklist and the last few user-facing activity
    # entries. The full log (incl. debug entries) is admin-only.
    seo_progress: dict | None = None


class ProjectStatusResponse(BaseModel):
    project_id: str
    status: str
    rejection_reason: str | None = None
    source_url: str
    blueprint: ProjectBlueprintSummary | None = None
    # One entry per tier that has finished generating so far -- populated
    # progressively as each tier succeeds, not only once the whole project
    # reaches "ready", so the UI can let the user switch between
    # already-finished tiers while others are still running.
    generations: list[ProjectGenerationSummary] = []
    tiers_total: int = 0
    tiers_completed: int = 0
    # Plural: tiers now fan out (see docs/concurrency-scaling-plan.md), so
    # more than one can be "running" at once, not just the tail of a chain.
    current_tiers: list[str] = []
    # Populated whenever an enabled tier's latest preview generation failed,
    # including on an otherwise-"ready" project where other tiers succeeded.
    tier_failures: list[ProjectTierFailure] = []
    # Only set while status == "awaiting_cost_approval" -- see
    # docs/generation-cost-gate-plan.md.
    cost_gate: GenerationCostGateInfo | None = None
    # Tiers the user has already paid to download -- re-downloading these
    # is free (download_spend is idempotent per project+tier).
    purchased_tiers: list[str] = []
    # Crawled page count -- "Generate all pages" is only offered when > 1.
    page_count: int = 1
    # Per finished tier: Generate all pages / Run SEO state.
    tier_actions: dict[str, ProjectTierActions] = {}
