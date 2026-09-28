from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_id: str
    category: str
    subcategory: str
    severity: str
    severity_base: str
    detection_type: str
    title: str
    component: str
    evidence: str
    evidence_lines: list[int]
    impact: str
    recommendation: str
    verification: str
    confidence: str
    context: str
    layer: str
    domain: str
    upstream_models: list[str]
    downstream_models: list[str]
    transitive_downstream_count: int
    impact_note: str
    ai_reasoning: str
    ai_evidence_cited: list[str]
    status: str
    reviewer_note: str
    created_at: dt.datetime


class FindingStatusUpdate(BaseModel):
    status: str  # New | Acknowledged | Needs Dev Fix | False Positive | Won't Fix
    reviewer_note: str = ""
