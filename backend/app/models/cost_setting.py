from datetime import datetime
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class CostSetting(Base):
    """Admin-editable global cost-gate numbers (see
    docs/generation-cost-gate-plan.md) -- `key` is a fixed, code-known name
    (e.g. "generation_cost_alert_usd", "usd_per_credit"), a missing row means
    "use the config.py/REDOWEBS_ env-var default", and a present row wins.
    Same override-the-config.py-default shape as AIModelSetting, but for a
    float value instead of a model id."""

    __tablename__ = "cost_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
