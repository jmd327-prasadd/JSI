from __future__ import annotations

from pathlib import Path

from app.rules.enrich import enrich_findings
from app.rules.finding_draft import FindingDraft
from app.rules.registry import registry


def evaluate_dbt_project(inv: dict) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    for detector in registry.detectors_for("dbt_project"):
        drafts.extend(detector(inv))
    return enrich_findings(inv, drafts)


def evaluate_security(root: Path) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    for detector in registry.detectors_for("any_text_file"):
        drafts.extend(detector(root))
    return drafts


def evaluate_inventory(inventory: dict, root: Path) -> list[FindingDraft]:
    """Run every deterministic rule over one artifact's discovered inventory.

    Snowflake-SQL-bundle and Power BI rule sets are not yet defined (no PoC
    precedent) -- classification/inventory for those components is captured
    (see discovery/inventory.py) but rule evaluation for them is a follow-up
    build step alongside the AI orchestration layer.
    """
    drafts: list[FindingDraft] = []
    for inv in inventory.get("dbt_projects", []):
        drafts.extend(evaluate_dbt_project(inv))
    drafts.extend(evaluate_security(root))
    return drafts


def draft_to_finding_kwargs(d: FindingDraft) -> dict:
    rule = registry.get(d.rule_id)
    severity = d.severity_override or rule.severity_default
    return dict(
        rule_id=d.rule_id,
        category=rule.category,
        subcategory=rule.subcategory,
        severity=severity,
        severity_base=rule.severity_default,
        detection_type=rule.detection_type,
        title=d.title,
        component=d.component,
        evidence=d.evidence,
        evidence_lines=d.evidence_lines,
        source_ref=d.source_ref,
        impact=d.impact,
        recommendation=d.recommendation,
        verification=d.verification,
        confidence=d.confidence,
        context=d.context,
        layer=d.layer,
        domain=d.domain,
        upstream_models=d.upstream_models,
        downstream_models=d.downstream_models,
        transitive_downstream_count=d.transitive_downstream_count,
        impact_note=d.impact_note,
    )
