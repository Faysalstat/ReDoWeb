from datetime import datetime

from pydantic import BaseModel


class AdminProjectListItem(BaseModel):
    project_id: str
    source_url: str
    status: str
    owner_email: str
    tier: str | None = None
    created_at: datetime


class AdminProjectListResponse(BaseModel):
    items: list[AdminProjectListItem]
    total: int
    page: int
    page_size: int


class AdminBlueprintSummary(BaseModel):
    site_name: str | None = None
    colors: dict | None = None
    fonts: dict | None = None
    tone: str | None = None
    version: int


class AdminGenerationOutputSummary(BaseModel):
    template_used: str
    preview_url_path: str
    summary: str | None = None
    contrast_warnings: list[str] = []
    prompt_tokens: int = 0
    completion_tokens: int = 0
    iterations: int = 0


class AdminGenerationJobSummary(BaseModel):
    job_id: str
    tier: str
    scope: str
    overall_status: str
    failure_reason: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    output: AdminGenerationOutputSummary | None = None
    # Resolved from TokenUsageLog (see
    # admin_analytics_service.get_token_usage_by_job) -- the authoritative
    # per-job source, since Tier.generation_model/AIModelSetting only
    # reflect the *current* config and can drift after this job ran.
    models_used: list[str] = []
    total_cost_usd: float = 0.0
    # Full step checklist + activity log (incl. debug entries: raw errors,
    # tokens/cost, per-page audit findings) -- see services/job_progress.py.
    # Currently written by SEO jobs only.
    progress: dict | None = None


class AdminPaidTier(BaseModel):
    tier: str
    credits: int
    charged_at: datetime


class AdminProjectDetailResponse(BaseModel):
    project_id: str
    source_url: str
    status: str
    rejection_reason: str | None = None
    owner_email: str
    owner_id: str
    created_at: datetime
    blueprint: AdminBlueprintSummary | None = None
    generation_jobs: list[AdminGenerationJobSummary]
    # Tiers the owner paid to download, from the download_spend ledger rows.
    paid_tiers: list[AdminPaidTier] = []
