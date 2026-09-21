from datetime import datetime

from pydantic import BaseModel


class AdminTierModelRow(BaseModel):
    key: str
    label: str
    is_active: bool
    generation_model: str | None = None
    effective_generation_model: str
    updated_at: datetime
    updated_by_admin_id: str | None = None


class AdminTierModelListResponse(BaseModel):
    items: list[AdminTierModelRow]


class AdminTierModelUpdateRequest(BaseModel):
    generation_model: str | None = None


class AdminTierActiveUpdateRequest(BaseModel):
    is_active: bool


class AdminVisionModelResponse(BaseModel):
    model_name: str | None = None
    effective_model_name: str
    updated_at: datetime | None = None
    updated_by_admin_id: str | None = None


class AdminVisionModelUpdateRequest(BaseModel):
    model_name: str
