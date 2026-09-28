from __future__ import annotations

from app.rules.finding_draft import FindingDraft
from app.rules.registry import registry


def model_meta_map(inv: dict) -> dict:
    return {m["name"]: m for m in inv.get("models_meta", [])}


def draft(rule_id: str, component: str, title: str, evidence: str, impact: str,
          recommendation: str, **kwargs) -> FindingDraft:
    confidence = kwargs.pop("confidence", None) or registry.confidence_for(rule_id)
    return FindingDraft(
        rule_id=rule_id, component=component, title=title, evidence=evidence,
        impact=impact, recommendation=recommendation, confidence=confidence, **kwargs,
    )
