import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class QueuedJob(Base):
    """Postgres-backed replacement for Celery's broker/result-backend
    (previously Redis) -- see CLAUDE.md. `queue_worker.py` claims rows with
    `SELECT ... FOR UPDATE SKIP LOCKED`, dispatches by `task_name`, and each
    pipeline stage enqueues the next stage's row on its own success path
    (same mechanism a Celery `chain` gave us: one link raising halts the
    pipeline since nothing further gets enqueued)."""

    __tablename__ = "queued_jobs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
