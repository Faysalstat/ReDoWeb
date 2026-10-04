from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import AIModelSetting, User
from ...schemas.admin.model_config import (
    AdminTierActiveUpdateRequest,
    AdminTierModelListResponse,
    AdminTierModelRow,
    AdminTierModelUpdateRequest,
    AdminVisionModelResponse,
    AdminVisionModelUpdateRequest,
)
from ...services import model_config_service, tier_service

router = APIRouter()


@router.get("/model-config/tiers", response_model=AdminTierModelListResponse)
def list_tier_models(db: Session = Depends(get_db)) -> AdminTierModelListResponse:
    tiers = tier_service.get_all_tiers(db)
    return AdminTierModelListResponse(
        items=[
            AdminTierModelRow(
                key=tier.key,
                label=tier.label,
                is_active=tier.is_active,
                generation_model=tier.generation_model,
                effective_generation_model=model_config_service.get_generation_model(tier.key, db),
                updated_at=tier.updated_at,
                updated_by_admin_id=str(tier.updated_by_admin_id) if tier.updated_by_admin_id else None,
            )
            for tier in tiers
        ]
    )


@router.put("/model-config/tiers/{key}", response_model=AdminTierModelRow)
def update_tier_model(
    key: str,
    body: AdminTierModelUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminTierModelRow:
    try:
        tier = tier_service.set_generation_model(key, body.generation_model, current_admin.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()

    return AdminTierModelRow(
        key=tier.key,
        label=tier.label,
        is_active=tier.is_active,
        generation_model=tier.generation_model,
        effective_generation_model=model_config_service.get_generation_model(tier.key, db),
        updated_at=tier.updated_at,
        updated_by_admin_id=str(tier.updated_by_admin_id) if tier.updated_by_admin_id else None,
    )


@router.patch("/model-config/tiers/{key}/active", response_model=AdminTierModelRow)
def update_tier_active(
    key: str,
    body: AdminTierActiveUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminTierModelRow:
    try:
        tier = tier_service.set_active(key, body.is_active, current_admin.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()

    return AdminTierModelRow(
        key=tier.key,
        label=tier.label,
        is_active=tier.is_active,
        generation_model=tier.generation_model,
        effective_generation_model=model_config_service.get_generation_model(tier.key, db),
        updated_at=tier.updated_at,
        updated_by_admin_id=str(tier.updated_by_admin_id) if tier.updated_by_admin_id else None,
    )


@router.get("/model-config/vision-model", response_model=AdminVisionModelResponse)
def get_vision_model(db: Session = Depends(get_db)) -> AdminVisionModelResponse:
    row = db.get(AIModelSetting, model_config_service.VISION_MODEL_KEY)
    return AdminVisionModelResponse(
        model_name=row.model_name if row is not None else None,
        effective_model_name=model_config_service.get_vision_model(db),
        updated_at=row.updated_at if row is not None else None,
        updated_by_admin_id=str(row.updated_by_admin_id) if row is not None and row.updated_by_admin_id else None,
    )


@router.put("/model-config/vision-model", response_model=AdminVisionModelResponse)
def update_vision_model(
    body: AdminVisionModelUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminVisionModelResponse:
    row = model_config_service.set_vision_model(body.model_name, current_admin.id, db)
    db.commit()

    return AdminVisionModelResponse(
        model_name=row.model_name,
        effective_model_name=model_config_service.get_vision_model(db),
        updated_at=row.updated_at,
        updated_by_admin_id=str(row.updated_by_admin_id) if row.updated_by_admin_id else None,
    )
