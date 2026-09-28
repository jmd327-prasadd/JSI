from __future__ import annotations

from app.rules.finding_draft import FindingDraft
from app.rules.detectors._common import draft, model_meta_map

# Ported from the JQA PoC (jqa/rules/all_rules.py). Detection logic is
# unchanged; each check is now its own function per the rule_id -> detector_ref
# mapping in app/rules/definitions/code.yaml, and severity/confidence are
# looked up from the rulebook rather than hardcoded.


def check_select_star(inv: dict) -> list[FindingDraft]:
    out = []
    for m in inv["models"]:
        if m["select_star"]:
            out.append(draft(
                "JQA-CODE-001", m["path"], "SELECT * detected",
                f"{m['path']} contains SELECT *.",
                "Schema changes can propagate unexpectedly and make support behaviour less predictable.",
                "Prefer explicit columns in governed/reporting models; document deliberate exceptions.",
                layer=m["layer"], domain=m["domain"],
            ))
    return out


def check_hardcoded_relation(inv: dict) -> list[FindingDraft]:
    out = []
    for m in inv["models"]:
        if m["hardcoded_relation"]:
            out.append(draft(
                "JQA-ARCH-001", m["path"], "Qualified database/schema reference detected",
                f"{m['path']} contains a qualified FROM/JOIN relation.",
                "Environment-specific references can complicate deployments and support investigations.",
                "Prefer dbt refs/sources where appropriate and document intentional cross-database references.",
                layer=m["layer"], domain=m["domain"],
            ))
    return out


def check_incremental_unique_key(inv: dict) -> list[FindingDraft]:
    out = []
    for m in inv["models"]:
        if m["is_incremental"] and not m["has_unique_key"]:
            out.append(draft(
                "JQA-OPS-001", m["path"], "Incremental model has no explicit unique_key",
                f"Incremental configuration detected without unique_key in {m['path']}.",
                "Reruns and deduplication can be harder to reason about during incident recovery.",
                "Validate the model grain and incremental strategy; define a key where required.",
                layer=m["layer"], domain=m["domain"],
            ))
    return out


def check_complexity(inv: dict) -> list[FindingDraft]:
    out = []
    for m in inv["models"]:
        if m["joins"] >= 8 or m["ctes"] >= 15 or m["lines"] >= 500:
            out.append(draft(
                "JQA-MNT-001", m["path"], "High SQL complexity detected",
                f"{m['lines']} lines, {m['joins']} joins, {m['ctes']} CTEs.",
                "Highly complex models can increase diagnosis time and change risk for support teams.",
                "Consider decomposition, clear interfaces and documentation; assess downstream dependency before prioritising remediation.",
                layer=m["layer"], domain=m["domain"],
            ))
    return out


def check_test_coverage(inv: dict) -> list[FindingDraft]:
    total = len(inv["models"])
    if not total:
        return []
    meta = model_meta_map(inv)
    tested = sum(1 for m in inv["models"] if meta.get(m["name"], {}).get("tests"))
    return [draft(
        "JQA-DQ-001", inv.get("dbt_project_path", "dbt_project.yml"),
        "No explicit dbt model test coverage was detected",
        f'{tested} of {total} discovered SQL models have tests/data_tests in schema.yml. '
        f'The standalone tests directory contains {len(inv["tests"])} SQL files.',
        "Without explicit repository-level dbt tests, data defects may reach downstream reporting without being caught by the project test suite.",
        "Define appropriate tests for business-critical models and key columns; validate whether any external/runtime controls exist before treating this as a complete quality gap.",
    )]


def check_legacy_source_naming(inv: dict) -> list[FindingDraft]:
    legacy = [s["name"] for s in inv["sources"] if "discontinued" in s["name"].lower()]
    if not legacy:
        return []
    return [draft(
        "JQA-OPS-003", inv.get("dbt_project_path", "dbt_project.yml"),
        "Legacy/discontinued source naming detected",
        "Review candidates: " + ", ".join(legacy),
        "Retained legacy objects can create uncertainty about ownership and whether dependencies still exist.",
        "Confirm downstream dependencies and business need; retire only after dependency validation.",
    )]
