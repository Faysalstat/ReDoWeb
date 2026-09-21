from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas.admin.earnings import AdminRevenueResponse
from ...services import admin_analytics_service

router = APIRouter()


@router.get("/earnings", response_model=AdminRevenueResponse)
def get_earnings(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)) -> AdminRevenueResponse:
    breakdown = admin_analytics_service.revenue_breakdown(db, days)
    return AdminRevenueResponse(**breakdown.__dict__)
