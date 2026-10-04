import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class PromptTemplate(Base):
    """Metadata for a design-strategy prompt file living on disk in
    backend/prompts/ -- the prompt TEXT is never duplicated into the DB,
    only filename/category/active-state/audit, mirroring AIModelSetting's
    audit shape. A file present in PROMPTS_DIR with no row here is treated
    as active (see prompt_template_service.get_active_template_filenames)
    -- this is what lets the pre-existing hand-written files keep working
    with zero required migration-time backfill, while an admin can still
    explicitly disable one later by inserting a row."""

    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    uploaded_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
