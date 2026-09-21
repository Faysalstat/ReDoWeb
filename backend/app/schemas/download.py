from typing import Literal

from pydantic import BaseModel


class DownloadStartResponse(BaseModel):
    status: Literal["ready", "building"]
    project_id: str
    tier: str
    job_id: str | None = None


class DownloadStatusResponse(BaseModel):
    status: Literal["ready", "building", "failed"]
    failure_reason: str | None = None
