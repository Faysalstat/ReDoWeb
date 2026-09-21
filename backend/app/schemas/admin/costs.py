from pydantic import BaseModel


class AdminModelCostRow(BaseModel):
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    call_count: int


class AdminModelCostResponse(BaseModel):
    items: list[AdminModelCostRow]


class AdminCostByUserRow(BaseModel):
    user_id: str
    email: str
    cost_usd: float
    call_count: int


class AdminCostByUserResponse(BaseModel):
    items: list[AdminCostByUserRow]
    total: int
    page: int
    page_size: int


class AdminCostByProjectRow(BaseModel):
    project_id: str
    source_url: str
    cost_usd: float
    call_count: int


class AdminCostByProjectResponse(BaseModel):
    items: list[AdminCostByProjectRow]
    total: int
    page: int
    page_size: int


class AdminModelPricingRow(BaseModel):
    model_name: str
    prompt_price_per_1m: float
    completion_price_per_1m: float
    updated_at: str | None = None
    updated_by_admin_id: str | None = None


class AdminModelPricingResponse(BaseModel):
    items: list[AdminModelPricingRow]


class AdminModelPricingUpdateRequest(BaseModel):
    prompt_price_per_1m: float
    completion_price_per_1m: float
