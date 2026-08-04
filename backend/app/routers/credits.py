from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..db.session import get_db
from ..models import User
from ..schemas.credits import WalletResponse
from ..services import wallet_service

router = APIRouter(prefix="/api/v1/credits", tags=["credits"])


@router.get("/wallet", response_model=WalletResponse)
def get_wallet(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> WalletResponse:
    wallet = wallet_service.get_or_create_wallet(db, current_user.id)
    db.commit()
    return WalletResponse(balance=wallet.balance)
