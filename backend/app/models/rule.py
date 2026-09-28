from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Rule(Base):
    """Mirrors the YAML rulebook (app/rules/definitions/*.yaml) into the DB for FK/reporting joins.

    The YAML files are the source of truth; this table is resynced on app startup.
    """

    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32))  # Code | Documentation | Environment
    subcategory: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    severity_default: Mapped[str] = mapped_column(String(16))  # Critical | High | Medium | Low
    # deterministic | llm_assisted | hybrid
    detection_type: Mapped[str] = mapped_column(String(16), default="deterministic")
    detector_ref: Mapped[str] = mapped_column(String(255), default="")
    trigger_ref: Mapped[str] = mapped_column(String(255), default="")
    judgment_ref: Mapped[str] = mapped_column(String(255), default="")
    applies_to: Mapped[str] = mapped_column(String(64), default="")
    remediation_template: Mapped[str] = mapped_column(Text, default="")
    verification_template: Mapped[str] = mapped_column(Text, default="")
    confidence_default: Mapped[str] = mapped_column(String(16), default="High")
