import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import User
from ...schemas.admin.credits import AdminAdjustmentResponse, AdminIssueAdjustmentRequest
from ...schemas.admin.projects import AdminProjectListItem
from ...schemas.admin.users import (
    AdminCreditLedgerEntry,
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
)
from ...services import admin_credits_service, admin_users_service
from ...services.wallet_service import InsufficientCreditsError

router = APIRouter()


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    result = admin_users_service.list_users(db, search=search, page=page, page_size=page_size)
    return AdminUserListResponse(
        items=[
            AdminUserListItem(
                user_id=str(item.user_id),
                email=item.email,
                is_admin=item.is_admin,
                is_active=item.is_active,
                wallet_balance=item.wallet_balance,
                projects_count=item.projects_count,
                created_at=item.created_at,
            )
            for item in result.items
        ],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user_detail(user_id: str, db: Session = Depends(get_db)) -> AdminUserDetailResponse:
    result = admin_users_service.get_user_detail(db, uuid.UUID(user_id))
    if result is None:
        raise HTTPException(status_code=404, detail=f"No user found for id {user_id}")

    return AdminUserDetailResponse(
        user_id=str(result.user.id),
        email=result.user.email,
        is_admin=result.user.is_admin,
        is_active=result.user.is_active,
        created_at=result.user.created_at,
        wallet_balance=result.wallet_balance,
        ledger=[
            AdminCreditLedgerEntry(
                id=str(txn.id),
                amount=txn.amount,
                reason=txn.reason,
                related_project_id=str(txn.related_project_id) if txn.related_project_id else None,
                related_job_id=str(txn.related_job_id) if txn.related_job_id else None,
                created_at=txn.created_at,
            )
            for txn in result.ledger
        ],
        projects=[
            AdminProjectListItem(
                project_id=str(item.project_id),
                source_url=item.source_url,
                status=item.status,
                owner_email=result.user.email,
                tier=item.tier,
                created_at=item.created_at,
            )
            for item in result.projects.items
        ],
    )


@router.post("/users/{user_id}/adjustments", response_model=AdminAdjustmentResponse)
def issue_adjustment(
    user_id: str,
    body: AdminIssueAdjustmentRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminAdjustmentResponse:
    try:
        result = admin_credits_service.issue_adjustment(
            db,
            user_id=uuid.UUID(user_id),
            amount=body.amount,
            note=body.note,
            admin_id=current_admin.id,
            related_project_id=uuid.UUID(body.related_project_id) if body.related_project_id else None,
        )
        db.commit()
    except InsufficientCreditsError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    return AdminAdjustmentResponse(
        wallet_balance=result.wallet.balance,
        transaction_id=str(result.transaction.id),
        purchase_id=str(result.purchase.id),
    )
