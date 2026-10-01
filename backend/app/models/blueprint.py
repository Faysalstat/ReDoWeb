import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class Blueprint(Base):
    """A version of a project's blueprint (scraped.json -> blueprint.json,
    see docs/blueprint-json-pipeline-plan.md). Versions are immutable --
    regenerating creates a new row and flips is_current, never overwrites.
    """

    __tablename__ = "blueprints"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_blueprint_project_version"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai_extracted")
    # Nullable: only populated via the design.md legacy-compat shim (kept so
    # site_generator.py -- out of scope for the structured-JSON pipeline --
    # keeps working unchanged) rather than being structurally required.
    design_md_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_json_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    blueprint_json_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    colors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    fonts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="blueprints")
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(back_populates="blueprint")
