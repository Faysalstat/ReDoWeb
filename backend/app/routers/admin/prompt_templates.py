from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import User
from ...schemas.admin.prompt_templates import (
    AdminPromptTemplateListResponse,
    AdminPromptTemplateRow,
    AdminPromptTemplateSetActiveRequest,
)
from ...services import prompt_template_service

router = APIRouter()


def _to_row(item) -> AdminPromptTemplateRow:
    return AdminPromptTemplateRow(
        filename=item.filename,
        category=item.category,
        is_active=item.is_active,
        uploaded_by_admin_id=str(item.uploaded_by_admin_id) if item.uploaded_by_admin_id else None,
        uploaded_at=item.uploaded_at,
    )


@router.get("/prompt-templates", response_model=AdminPromptTemplateListResponse)
def list_prompt_templates(db: Session = Depends(get_db)) -> AdminPromptTemplateListResponse:
    items = prompt_template_service.get_all_templates_for_admin_view(db)
    return AdminPromptTemplateListResponse(items=[_to_row(item) for item in items])


@router.post("/prompt-templates", response_model=AdminPromptTemplateRow, status_code=201)
async def upload_prompt_template(
    category: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminPromptTemplateRow:
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=422, detail="only .txt files are accepted")

    content = await file.read()
    try:
        row = prompt_template_service.save_uploaded_template(
            db, category=category, raw_name=name, content=content, admin_id=current_admin.id
        )
        db.commit()
    except (ValueError, FileExistsError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    return _to_row(row)


@router.patch("/prompt-templates/{filename}", response_model=AdminPromptTemplateRow)
def set_prompt_template_active(
    filename: str,
    body: AdminPromptTemplateSetActiveRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminPromptTemplateRow:
    try:
        row = prompt_template_service.set_active(db, filename, body.is_active, current_admin.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    return _to_row(row)


@router.delete("/prompt-templates/{filename}", status_code=204)
def delete_prompt_template(filename: str, db: Session = Depends(get_db)) -> None:
    try:
        prompt_template_service.delete_template(db, filename)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
