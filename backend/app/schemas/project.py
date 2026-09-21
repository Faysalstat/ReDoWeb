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
