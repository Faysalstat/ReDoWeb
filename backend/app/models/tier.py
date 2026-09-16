import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class Tier(Base):
    """DB-backed replacement for the hardcoded list in tier_service.py.
    `key` is immutable after creation -- it's embedded in generation_jobs.tier
    and storage paths (generated/{key}/), so renaming it would orphan
    history. Enforced at the service/router layer, not the DB."""

    __tablename__ = "tiers"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    download_credit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    # OpenRouter model id used for this tier's site-generation agent loop
    # (see site_generator._run_agent_loop). NULL means "use the
    # config.py/REDOWEBS_GENERATION_MODEL default" -- lets an admin pin an
    # individual tier to a specific model (e.g. a cheaper one for a lower
    # tier) by editing this row, with no rebuild/redeploy.
    generation_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
