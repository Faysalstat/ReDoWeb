"""Tiers & pricing page: label, display order, on/off and download cost per
tier. The AI model per tier stays on Model config (routers/admin/
model_config.py)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import User
from ...schemas.admin.tiers import AdminTierActiveRequest, AdminTierListResponse, AdminTierRow, AdminTierUpdateRequest
from ...services import tier_service

router = APIRouter()


def _row(tier: tier_service.Tier) -> AdminTierRow:
    return AdminTierRow(
        key=tier.key,
        label=tier.label,
        is_active=tier.is_active,
        sort_order=tier.sort_order,
        download_credit_cost=tier.download_credit_cost,
        updated_at=tier.updated_at,
        updated_by_admin_id=str(tier.updated_by_admin_id) if tier.updated_by_admin_id else None,
    )


@router.get("/tiers", response_model=AdminTierListResponse)
def list_tiers(db: Session = Depends(get_db)) -> AdminTierListResponse:
    return AdminTierListResponse(items=[_row(t) for t in tier_service.get_all_tiers(db)])


@router.put("/tiers/{key}", response_model=AdminTierRow)
def update_tier(
    key: str,
    body: AdminTierUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminTierRow:
    try:
        tier = tier_service.update_tier(
            key,
            label=body.label,
            sort_order=body.sort_order,
            download_credit_cost=body.download_credit_cost,
            admin_id=current_admin.id,
            db=db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _row(tier)


@router.patch("/tiers/{key}/active", response_model=AdminTierRow)
def set_tier_active(
    key: str,
    body: AdminTierActiveRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminTierRow:
    try:
        tier = tier_service.set_active(key, body.is_active, current_admin.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return _row(tier)
