import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set together when tasks_blueprint.py's cost-estimate gate pauses the
    # pipeline (status == "awaiting_cost_approval") instead of fanning out
    # generate_tier jobs -- see docs/generation-cost-gate-plan.md.
    # pending_tier_keys snapshots the enabled tiers *at gate time*, so
    # POST /projects/{id}/approve-generation enqueues exactly what was
    # quoted even if an admin disables a tier while the project waits.
    estimated_generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pending_tier_keys: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Set by storage_cleanup_service once the project is past the retention
    # window: its crawl snapshot and every UNPURCHASED tier preview are gone
    # from disk (purchased designs are kept). Unpurchased tiers can no
    # longer be bought or retried after this.
    previews_expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Admin soft delete (services/project_deletion_service.py): every file on
    # disk is removed, but this row and all its history (jobs, costs, ledger,
    # submission log) stay. Hidden from the owner (404) once set.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    deletion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tos_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # foreign_keys is required: deleted_by_admin_id is a second FK to users.
    owner: Mapped["User"] = relationship(foreign_keys=[user_id])
    crawl_snapshots: Mapped[list["CrawlSnapshot"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    blueprints: Mapped[list["Blueprint"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class SubmissionLog(Base):
    """Append-only record of every crawl submission, kept for abuse/DMCA
    response purposes -- never edited or deleted (see docs/PRD.md)."""

    __tablename__ = "submission_logs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    tos_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrawlSnapshot(Base):
    __tablename__ = "crawl_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crawl_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    crawl_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="crawl_snapshots")
    pages: Mapped[list["CrawlPage"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class CrawlPage(Base):
    __tablename__ = "crawl_pages"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crawl_snapshots.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped["CrawlSnapshot"] = relationship(back_populates="pages")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="assets")
