from __future__ import annotations

import datetime as dt

from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid


class Document(Base):
    """A handover documentation upload (PDF/Word), converted to Markdown before any LLM use."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    original_filename: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))  # pdf | docx
    storage_path: Mapped[str] = mapped_column(String(1024))
    converted_markdown_path: Mapped[str] = mapped_column(String(1024), default="")
    # pending -> converting -> converted -> failed
    conversion_status: Mapped[str] = mapped_column(String(32), default="pending")
    conversion_tool: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="documents")
    sections: Mapped[list["DocSection"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocSection(Base):
    __tablename__ = "doc_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"))
    heading_path: Mapped[str] = mapped_column(String(1024), default="")
    heading_level: Mapped[int] = mapped_column(Integer, default=1)
    # architecture | data_flow | business_logic | rca | runbook | glossary | sla | security | dependencies | other
    section_type: Mapped[str] = mapped_column(String(32), default="other")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    markdown_body: Mapped[str] = mapped_column(Text, default="")
    llm_eligible: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="sections")
