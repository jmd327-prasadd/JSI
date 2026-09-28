from __future__ import annotations

from app.rules.finding_draft import FindingDraft
from app.rules.detectors._common import draft, model_meta_map


def check_model_description_coverage(inv: dict) -> list[FindingDraft]:
    total = len(inv["models"])
    if not total:
        return []
    meta = model_meta_map(inv)
    documented = sum(1 for m in inv["models"] if meta.get(m["name"], {}).get("description"))
    return [draft(
        "JQA-DOC-001", inv.get("dbt_project_path", "dbt_project.yml"),
        "Model metadata coverage is limited",
        f"{documented} of {total} discovered SQL models have a matching model definition "
        f"with a description ({documented / total:.1%}).",
        "Incomplete metadata increases onboarding and incident-triage effort for Managed Services, "
        "particularly for production-facing models.",
        "Prioritise documentation for presentation-layer and highly connected production models; "
        "capture purpose, grain, business meaning and assumptions.",
    )]


def check_source_description_coverage(inv: dict) -> list[FindingDraft]:
    missing = [s["name"] for s in inv["sources"] if not s.get("description")]
    if not missing:
        return []
    return [draft(
        "JQA-DOC-002", inv.get("dbt_project_path", "dbt_project.yml"),
        "Source metadata descriptions are incomplete",
        f'{len(missing)} of {len(inv["sources"])} discovered sources have no source-level description.',
        "Missing source context can increase upstream tracing effort during incidents and handover.",
        "Document source purpose, owner, expected role and important operational assumptions for critical sources.",
    )]
