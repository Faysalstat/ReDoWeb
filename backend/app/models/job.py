import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("blueprints.id"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    # "preview" (the initial home-page-only tiered generation, every job
    # before 2026-09-17), "full_site" (the purchased "Generate all pages"
    # multi-page build -- see workers/tasks_full_site.py) or "seo" (the
    # purchased Pro/Premium SEO pass -- see workers/tasks_seo.py).
    # downloads.py uses this to tell the kinds of job apart for the same
    # (project, tier).
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="preview")
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Live step/percent/activity log while the job runs (currently written
    # by the SEO pass -- see services/job_progress.py). Kept after the job
    # finishes, so it doubles as the run's audit log.
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="generation_jobs")
    blueprint: Mapped["Blueprint"] = relationship(back_populates="generation_jobs")
    output: Mapped["GenerationOutput | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )


class GenerationOutput(Base):
    __tablename__ = "generation_outputs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generation_jobs.id"), nullable=False
    )
    template_used: Mapped[str] = mapped_column(String(255), nullable=False)
    output_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    preview_url_path: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contrast_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    alt_text_added: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    og_tags_added: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    reveal_visibility_fixes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sitemap_written: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # scope="seo" jobs only: audit before/after + every mechanical fix the
    # SEO finalizer applied (see app/ai/seo_agent.py).
    seo_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # scope="full_site" jobs only: what the deterministic design-consistency
    # guards changed (see app/ai/site_consistency.py).
    consistency_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["GenerationJob"] = relationship(back_populates="output")
