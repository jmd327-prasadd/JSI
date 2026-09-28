from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid


class Artifact(Base):
    """A ZIP code-bundle upload for a project (dbt / raw Snowflake SQL / Power BI project, etc)."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(32), default="code_zip")
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    # pending -> extracting -> extracted -> failed
    extraction_status: Mapped[str] = mapped_column(String(32), default="pending")
    inventory_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="artifacts")
