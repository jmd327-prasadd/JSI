from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid

RUN_STAGES = [
    "queued",
    "extracting",
    "discovering",
    "converting_docs",
    "building_graph",
    "evaluating_rules",
    "llm_judgment",
    "aggregating",
    "done",
    "failed",
]


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    status_message: Mapped[str] = mapped_column(String(512), default="")
    inventory_path: Mapped[str] = mapped_column(String(1024), default="")
    read_plan_path: Mapped[str] = mapped_column(String(1024), default="")
    llm_token_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="runs")
    findings: Mapped[list["Finding"]] = relationship(back_populates="run", cascade="all, delete-orphan")
