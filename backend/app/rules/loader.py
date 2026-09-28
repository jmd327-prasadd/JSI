from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.rule import Rule
from app.rules.registry import registry


def sync_rules_to_db(db: Session) -> None:
    """Mirror the YAML rulebook (source of truth) into the `rules` table.
    Called on app startup; upserts every rule, never deletes -- a rule
    retired from YAML simply stops being resolvable for new findings.
    """
    for rule_def in registry.all():
        row = db.get(Rule, rule_def.rule_id)
        if row is None:
            row = Rule(rule_id=rule_def.rule_id)
            db.add(row)
        row.category = rule_def.category
        row.subcategory = rule_def.subcategory
        row.title = rule_def.title
        row.description = rule_def.description
        row.severity_default = rule_def.severity_default
        row.detection_type = rule_def.detection_type
        row.detector_ref = rule_def.detector_ref
        row.trigger_ref = rule_def.trigger_ref
        row.judgment_ref = rule_def.judgment_ref
        row.applies_to = rule_def.applies_to
        row.remediation_template = rule_def.remediation_template
        row.verification_template = rule_def.verification_template
        row.confidence_default = rule_def.confidence_default
    db.commit()
