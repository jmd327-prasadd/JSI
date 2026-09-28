from __future__ import annotations

from app.rules.finding_draft import FindingDraft
from app.rules.registry import registry


def enrich_findings(inv: dict, drafts: list[FindingDraft]) -> list[FindingDraft]:
    """Add dependency-graph context/impact_note and the rulebook's verification
    template to each finding, without changing detector-produced evidence.
    Ported from the JQA PoC's enrich_findings(), generalized to source
    verification text from the rulebook instead of a hardcoded if/elif chain.
    """
    model_by_path = {m["path"]: m for m in inv.get("models", [])}
    for f in drafts:
        m = model_by_path.get(f.component)
        if m:
            f.context = (
                f"Layer: {m.get('layer') or 'unknown'}; domain: {m.get('domain') or 'unknown'}; "
                f"SQL size: {m.get('lines', 0)} lines; joins: {m.get('joins', 0)}; CTEs: {m.get('ctes', 0)}."
            )
            dep = inv.get("dependencies", {}).get("nodes", {}).get(m["name"], {})
            ups = [x for x in dep.get("upstream", []) if not x.startswith("source:")]
            downs = [x for x in dep.get("downstream", []) if not x.startswith("source:")]
            f.upstream_models = ups
            f.downstream_models = downs
            f.transitive_downstream_count = dep.get("transitive_downstream_count", 0)
            if downs:
                shown = ", ".join(downs[:6])
                if len(downs) > 6:
                    shown += f" + {len(downs) - 6} more"
                f.impact_note = f"Direct downstream models: {shown}."
            elif f.transitive_downstream_count:
                f.impact_note = (
                    f"This model has {f.transitive_downstream_count} downstream model "
                    "dependencies in the inspected graph."
                )
            else:
                f.impact_note = "No downstream model dependency was detected from explicit dbt ref() relationships."
        else:
            f.context = "Repository-level observation; runtime configuration or deployment state may require separate validation."
            f.impact_note = "Dependency impact could not be tied to a specific SQL model."

        try:
            f.verification = registry.get(f.rule_id).verification_template or f.verification
        except KeyError:
            pass
    return drafts
