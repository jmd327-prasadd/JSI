from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import String, DateTime, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_runs.id"))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    rule_id: Mapped[str] = mapped_column(String(64), ForeignKey("rules.rule_id"))

    category: Mapped[str] = mapped_column(String(32))
    subcategory: Mapped[str] = mapped_column(String(64), default="")
    severity: Mapped[str] = mapped_column(String(16))
    severity_base: Mapped[str] = mapped_column(String(16))
    detection_type: Mapped[str] = mapped_column(String(16), default="deterministic")

    title: Mapped[str] = mapped_column(String(255))
    component: Mapped[str] = mapped_column(String(1024))  # file path or doc-section ref, human readable
    evidence: Mapped[str] = mapped_column(Text, default="")
    evidence_lines: Mapped[list[int]] = mapped_column(JSON, default=list)
    source_ref: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    impact: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(16), default="High")
    context: Mapped[str] = mapped_column(Text, default="")

    layer: Mapped[str] = mapped_column(String(64), default="")
    domain: Mapped[str] = mapped_column(String(64), default="")
    upstream_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    downstream_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    transitive_downstream_count: Mapped[int] = mapped_column(Integer, default=0)
    impact_note: Mapped[str] = mapped_column(Text, default="")

    # AI-assisted findings only (see app/schemas/llm_judgment.py)
    ai_reasoning: Mapped[str] = mapped_column(Text, default="")
    ai_evidence_cited: Mapped[list[str]] = mapped_column(JSON, default=list)
    ai_model_used: Mapped[str] = mapped_column(String(128), default="")
    ai_prompt_version: Mapped[str] = mapped_column(String(32), default="")

    # Review workflow (human triage before this feeds an onboard/bounce decision)
    # New -> Acknowledged | Needs Dev Fix | False Positive | Won't Fix
    status: Mapped[str] = mapped_column(String(32), default="New")
    reviewer_note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    run: Mapped["AnalysisRun"] = relationship(back_populates="findings")
