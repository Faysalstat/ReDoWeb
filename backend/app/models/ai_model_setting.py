from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AIModelSetting(Base):
    """Admin-editable override for a non-tier-specific OpenRouter model id
    (currently just the shared vision/review model used by every
    blueprint_review.py call -- see model_config_service.get_vision_model).
    Mirrors ModelPricing's
    override-the-config.py-default pattern: `key` is a fixed, code-known
    name (e.g. "vision_model"), a missing row means "use the config.py/
    REDOWEBS_ env-var default", and a present row wins."""

    __tablename__ = "ai_model_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
