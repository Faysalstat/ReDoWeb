from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import ModelPricing, User
from ...schemas.admin.costs import (
    AdminCostByProjectResponse,
    AdminCostByProjectRow,
    AdminCostByUserResponse,
    AdminCostByUserRow,
    AdminModelCostResponse,
    AdminModelCostRow,
    AdminModelPricingResponse,
    AdminModelPricingRow,
    AdminModelPricingUpdateRequest,
)
from ...services import admin_analytics_service

router = APIRouter()


@router.get("/costs/by-model", response_model=AdminModelCostResponse)
def get_cost_by_model(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)) -> AdminModelCostResponse:
    rows = admin_analytics_service.cost_by_model(db, days)
    return AdminModelCostResponse(
        items=[
            AdminModelCostRow(
                model_name=row.model_name,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                cost_usd=row.cost_usd,
                call_count=row.call_count,
            )
            for row in rows
        ]
    )


@router.get("/costs/by-user", response_model=AdminCostByUserResponse)
def get_cost_by_user(
    days: int = Query(default=30, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminCostByUserResponse:
    result = admin_analytics_service.cost_by_user(db, days, page, page_size)
    return AdminCostByUserResponse(
        items=[
            AdminCostByUserRow(user_id=str(row.user_id), email=row.email, cost_usd=row.cost_usd, call_count=row.call_count)
            for row in result.items
        ],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/costs/by-project", response_model=AdminCostByProjectResponse)
def get_cost_by_project(
    days: int = Query(default=30, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminCostByProjectResponse:
    result = admin_analytics_service.cost_by_project(db, days, page, page_size)
    return AdminCostByProjectResponse(
        items=[
            AdminCostByProjectRow(
                project_id=str(row.project_id), source_url=row.source_url, cost_usd=row.cost_usd, call_count=row.call_count
            )
            for row in result.items
        ],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/model-pricing", response_model=AdminModelPricingResponse)
def list_model_pricing(db: Session = Depends(get_db)) -> AdminModelPricingResponse:
    rows = db.scalars(select(ModelPricing)).all()
    return AdminModelPricingResponse(
        items=[
            AdminModelPricingRow(
                model_name=row.model_name,
                prompt_price_per_1m=float(row.prompt_price_per_1m),
                completion_price_per_1m=float(row.completion_price_per_1m),
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
                updated_by_admin_id=str(row.updated_by_admin_id) if row.updated_by_admin_id else None,
            )
            for row in rows
        ]
    )


@router.put("/model-pricing/{model_name:path}", response_model=AdminModelPricingRow)
def upsert_model_pricing(
    model_name: str,
    body: AdminModelPricingUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminModelPricingRow:
    row = db.get(ModelPricing, model_name)
    if row is None:
        row = ModelPricing(
            model_name=model_name,
            prompt_price_per_1m=body.prompt_price_per_1m,
            completion_price_per_1m=body.completion_price_per_1m,
            updated_by_admin_id=current_admin.id,
        )
        db.add(row)
    else:
        row.prompt_price_per_1m = body.prompt_price_per_1m
        row.completion_price_per_1m = body.completion_price_per_1m
        row.updated_by_admin_id = current_admin.id
    db.commit()
    db.refresh(row)

    return AdminModelPricingRow(
        model_name=row.model_name,
        prompt_price_per_1m=float(row.prompt_price_per_1m),
        completion_price_per_1m=float(row.completion_price_per_1m),
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        updated_by_admin_id=str(row.updated_by_admin_id) if row.updated_by_admin_id else None,
    )
