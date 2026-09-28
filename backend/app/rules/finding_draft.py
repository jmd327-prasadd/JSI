from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FindingDraft:
    """In-memory finding produced by a detector, before it's resolved against
    the rule registry (for category/detection_type) and persisted as a DB Finding.

    Field shape is carried over from the original JQA PoC's Finding dataclass
    (jqa/models.py) -- the 4-part narrative (evidence / impact / recommendation
    / verification) is preserved as-is.
    """

    rule_id: str
    component: str
    title: str
    evidence: str
    impact: str
    recommendation: str
    confidence: str = "Medium"
    severity_override: str = ""  # only set when a detector needs to deviate from the rule's severity_default
    layer: str = ""
    domain: str = ""
    evidence_lines: list[int] = field(default_factory=list)
    context: str = ""
    verification: str = ""
    upstream_models: list[str] = field(default_factory=list)
    downstream_models: list[str] = field(default_factory=list)
    transitive_downstream_count: int = 0
    impact_note: str = ""
    source_ref: dict = field(default_factory=dict)
