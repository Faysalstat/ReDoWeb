from typing import Literal

from pydantic import BaseModel


class PurchaseResponse(BaseModel):
    purchased: bool
    project_id: str
    tier: str


class DownloadStartResponse(BaseModel):
    """Deprecated POST /download alias response -- kept only so a browser
    tab still running the pre-Buy-split frontend keeps working after
    deploy. Always "ready": purchase no longer auto-starts a build."""

    status: Literal["ready", "building"]
    project_id: str
    tier: str
    job_id: str | None = None


class ActionStartResponse(BaseModel):
    """POST /full-site and POST /seo: the action is (now) running."""

    status: Literal["running"]
    project_id: str
    tier: str
    job_id: str
