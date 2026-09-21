from datetime import datetime

from pydantic import BaseModel


class AdminPromptTemplateRow(BaseModel):
    filename: str
    category: str
    is_active: bool
    uploaded_by_admin_id: str | None = None
    uploaded_at: datetime | None = None


class AdminPromptTemplateListResponse(BaseModel):
    items: list[AdminPromptTemplateRow]


class AdminPromptTemplateSetActiveRequest(BaseModel):
    is_active: bool
