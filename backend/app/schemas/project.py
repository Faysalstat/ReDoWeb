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
    generation: ProjectGenerationSummary | None = None
