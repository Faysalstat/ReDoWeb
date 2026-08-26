from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ModelPricing(Base):
    """Admin-editable USD-per-1M-token pricing, overriding
    token_usage_service.MODEL_PRICING_PER_1M (which stays as the seed/
    fallback). Exists because that hardcoded dict silently priced the live
    `anthropic/claude-opus-5` generation model at $0.00 -- unpriced models
    should require a deliberate admin action, not a deploy."""

    __tablename__ = "model_pricing"

    model_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    prompt_price_per_1m: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    completion_price_per_1m: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
