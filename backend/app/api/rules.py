from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.rules.registry import registry

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleOut(BaseModel):
    rule_id: str
    category: str
    subcategory: str
    title: str
    description: str
    severity_default: str
    detection_type: str
    confidence_default: str


@router.get("", response_model=list[RuleOut])
def list_rules() -> list[RuleOut]:
    return [
        RuleOut(
            rule_id=r.rule_id, category=r.category, subcategory=r.subcategory,
            title=r.title, description=r.description, severity_default=r.severity_default,
            detection_type=r.detection_type, confidence_default=r.confidence_default,
        )
        for r in sorted(registry.all(), key=lambda r: r.rule_id)
    ]
