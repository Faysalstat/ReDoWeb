from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import User
from ...schemas.admin.overview import AdminOverviewResponse
from ...services import admin_analytics_service

router = APIRouter()


@router.get("/overview", response_model=AdminOverviewResponse)
def get_overview(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminOverviewResponse:
    stats = admin_analytics_service.get_overview(db, days)
    payments = admin_analytics_service.payment_stats(db, days)
    return AdminOverviewResponse(**stats.__dict__, **payments.__dict__)
