import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import CreditPack, User
from ...schemas.admin.credit_packs import (
    AdminCreditPackActiveRequest,
    AdminCreditPackCreateRequest,
    AdminCreditPackListResponse,
    AdminCreditPackRow,
    AdminCreditPackUpdateRequest,
)
from ...services import credit_pack_service
from ...services.credit_pack_service import CreditPackNotFoundError

router = APIRouter()


def _row(pack: CreditPack) -> AdminCreditPackRow:
    return AdminCreditPackRow(
        id=str(pack.id),
        name=pack.name,
        credits=pack.credits,
        price_usd_cents=pack.price_usd_cents,
        is_active=pack.is_active,
        sort_order=pack.sort_order,
        updated_at=pack.updated_at,
        updated_by_admin_id=str(pack.updated_by_admin_id) if pack.updated_by_admin_id else None,
    )


@router.get("/credit-packs", response_model=AdminCreditPackListResponse)
def list_credit_packs(db: Session = Depends(get_db)) -> AdminCreditPackListResponse:
    return AdminCreditPackListResponse(items=[_row(p) for p in credit_pack_service.list_all(db)])


@router.post("/credit-packs", response_model=AdminCreditPackRow, status_code=201)
def create_credit_pack(
    body: AdminCreditPackCreateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminCreditPackRow:
    try:
        pack = credit_pack_service.create(
            db,
            name=body.name,
            credits=body.credits,
            price_usd_cents=body.price_usd_cents,
            is_active=body.is_active,
            sort_order=body.sort_order,
            admin_id=current_admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return _row(pack)


@router.put("/credit-packs/{pack_id}", response_model=AdminCreditPackRow)
def update_credit_pack(
    pack_id: uuid.UUID,
    body: AdminCreditPackUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminCreditPackRow:
    try:
        pack = credit_pack_service.update(
            db,
            pack_id,
            name=body.name,
            credits=body.credits,
            price_usd_cents=body.price_usd_cents,
            sort_order=body.sort_order,
            admin_id=current_admin.id,
        )
    except CreditPackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return _row(pack)


@router.patch("/credit-packs/{pack_id}/active", response_model=AdminCreditPackRow)
def set_credit_pack_active(
    pack_id: uuid.UUID,
    body: AdminCreditPackActiveRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminCreditPackRow:
    try:
        pack = credit_pack_service.set_active(db, pack_id, body.is_active, current_admin.id)
    except CreditPackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return _row(pack)

