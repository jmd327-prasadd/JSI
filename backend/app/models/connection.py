from __future__ import annotations

from typing import Any

from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid


class Connection(Base):
    """Placeholder for a future live environment connector (Snowflake/CI-CD/billing/orchestration).

    v1 stores stub rows only -- no live analysis is performed against these.
    """

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    connector_type: Mapped[str] = mapped_column(String(64))  # snowflake | fivetran | cicd | billing | orchestration
    status: Mapped[str] = mapped_column(String(32), default="not_configured")
    config_placeholder: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="connections")
