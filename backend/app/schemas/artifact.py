from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    size_bytes: int
    extraction_status: str
    inventory_summary: dict[str, Any]
    created_at: dt.datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    file_type: str
    conversion_status: str
    created_at: dt.datetime
