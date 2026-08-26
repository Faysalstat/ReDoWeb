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


class AdminGenerationJobSummary(BaseModel):
    job_id: str
    tier: str
    overall_status: str
    failure_reason: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    output: AdminGenerationOutputSummary | None = None


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
