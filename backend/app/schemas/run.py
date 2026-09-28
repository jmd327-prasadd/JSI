from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    progress_pct: int
    status_message: str
    error_message: str
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None


class RunSummary(BaseModel):
    run_id: str
    status: str
    counts_by_severity: dict[str, int]
    counts_by_category: dict[str, int]
    total_findings: int
    traffic_light_by_category: dict[str, str]
    readiness_score_by_category: dict[str, int]
    recommended_action: str
    punch_list: list[str]
