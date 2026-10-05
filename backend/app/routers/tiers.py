from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.billing import PublicTierListResponse, PublicTierResponse
from ..services import tier_service

router = APIRouter(prefix="/api/v1", tags=["tiers"])


@router.get("/tiers", response_model=PublicTierListResponse)
def list_active_tiers(db: Session = Depends(get_db)) -> PublicTierListResponse:
    """Public (no login) -- the pricing page and download buttons show each
    enabled tier's real download cost from here."""
    return PublicTierListResponse(
        items=[
            PublicTierResponse(key=t.key, label=t.label, download_credit_cost=t.download_credit_cost)
            for t in tier_service.get_enabled_tiers(db)
        ]
    )
