from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import CostSetting, User
from ...schemas.admin.cost_gate_config import AdminCostSettingResponse, AdminCostSettingUpdateRequest
from ...services import cost_settings_service

router = APIRouter()


def _response(key: str, effective_value: float, db: Session) -> AdminCostSettingResponse:
    row = db.get(CostSetting, key)
    return AdminCostSettingResponse(
        value=effective_value,
        is_default=row is None,
        updated_at=row.updated_at if row is not None else None,
        updated_by_admin_id=str(row.updated_by_admin_id) if row is not None and row.updated_by_admin_id else None,
    )


@router.get("/cost-gate/threshold", response_model=AdminCostSettingResponse)
def get_cost_alert_threshold(db: Session = Depends(get_db)) -> AdminCostSettingResponse:
    return _response(
        cost_settings_service.GENERATION_COST_ALERT_USD_KEY,
        cost_settings_service.get_generation_cost_alert_usd(db),
        db,
    )


@router.put("/cost-gate/threshold", response_model=AdminCostSettingResponse)
def update_cost_alert_threshold(
    body: AdminCostSettingUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminCostSettingResponse:
    cost_settings_service.set_generation_cost_alert_usd(body.value, current_admin.id, db)
    db.commit()
    return _response(
        cost_settings_service.GENERATION_COST_ALERT_USD_KEY,
        cost_settings_service.get_generation_cost_alert_usd(db),
        db,
    )


@router.get("/cost-gate/usd-per-credit", response_model=AdminCostSettingResponse)
def get_usd_per_credit(db: Session = Depends(get_db)) -> AdminCostSettingResponse:
    return _response(
        cost_settings_service.USD_PER_CREDIT_KEY, cost_settings_service.get_usd_per_credit(db), db
    )


@router.put("/cost-gate/usd-per-credit", response_model=AdminCostSettingResponse)
def update_usd_per_credit(
    body: AdminCostSettingUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminCostSettingResponse:
    cost_settings_service.set_usd_per_credit(body.value, current_admin.id, db)
    db.commit()
    return _response(
        cost_settings_service.USD_PER_CREDIT_KEY, cost_settings_service.get_usd_per_credit(db), db
    )
