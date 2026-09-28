from __future__ import annotations

import re

from app.rules.finding_draft import FindingDraft
from app.rules.detectors._common import draft


def check_source_freshness(inv: dict) -> list[FindingDraft]:
    missing_fresh = [
        s["name"] for s in inv["sources"]
        if not s.get("freshness") and s["name"] not in {"rawtest", "wiptest"}
    ]
    if not missing_fresh:
        return []
    return [draft(
        "JQA-OPS-002", inv.get("dbt_project_path", "dbt_project.yml"),
        "Operational sources have no declared dbt freshness configuration",
        f"{len(missing_fresh)} sources have no freshness block; test-looking sources were excluded from this aggregate.",
        "Without declared freshness expectations, stale upstream data may be harder to detect before users report it.",
        "Define freshness expectations for sources where timeliness is operationally important; "
        "confirm actual ingestion SLAs before setting thresholds.",
    )]


def check_multiple_workflows(inv: dict) -> list[FindingDraft]:
    if len(inv["workflows"]) <= 1:
        return []
    return [draft(
        "JQA-CICD-001", "/.github/workflows", "Multiple GitHub Actions workflow definitions detected",
        "Workflow files: " + ", ".join(w["path"] for w in inv["workflows"]),
        "Overlapping pipelines can make the authoritative deployment path harder for Managed Services to identify.",
        "Document the purpose and ownership of each workflow and identify the authoritative CI/CD path.",
    )]


def check_workflow_with_casing(inv: dict) -> list[FindingDraft]:
    out = []
    for w in inv["workflows"]:
        if re.search(r"^\s+WITH:\s*$", w["text"], re.M):
            out.append(draft(
                "JQA-CICD-002", w["path"], "GitHub Actions action input key uses unexpected casing",
                "The workflow contains a `WITH:` key where GitHub Actions action inputs conventionally use `with:`.",
                "If interpreted as invalid workflow syntax, setup/upload steps may fail or behave differently from intended.",
                "Validate the workflow with GitHub Actions; change the key to the supported syntax if confirmed.",
            ))
    return out


def check_workflow_branch_mismatch(inv: dict) -> list[FindingDraft]:
    out = []
    for w in inv["workflows"]:
        t = w["text"]
        trigger_block = t[t.find("on:"):t.find("jobs:")] if "on:" in t and "jobs:" in t else ""
        triggers = set(re.findall(r"^\s*-\s*([A-Za-z0-9_-]+)\s*$", trigger_block, re.M))
        if re.search(r"if:\s*github\.ref\s*==\s*['\"]refs/heads/main['\"]", t) and triggers and "main" not in triggers:
            out.append(draft(
                "JQA-CICD-003", w["path"], "Deployment condition does not match configured branch trigger",
                "A deployment job is gated on refs/heads/main while the workflow trigger block does not list main as a push branch.",
                "The deployment job may be unreachable through the configured push trigger, creating operational uncertainty in release handling.",
                "Validate intended branch strategy and align workflow triggers and deployment conditions.",
            ))
    return out


def check_unpinned_dbt_version(inv: dict) -> list[FindingDraft]:
    out = []
    for w in inv["workflows"]:
        if re.search(r"pip\s+install\s+.*dbt-(?:core|snowflake)(?![=<>~])", w["text"]):
            out.append(draft(
                "JQA-CICD-004", w["path"], "dbt CI dependency versions are not pinned",
                "The workflow installs dbt packages without explicit version constraints.",
                "Unpinned CI dependencies can change between runs and complicate reproducibility during support or recovery.",
                "Pin compatible dbt-core/dbt-snowflake versions and update them deliberately.",
            ))
    return out


def check_hardcoded_runner_path(inv: dict) -> list[FindingDraft]:
    out = []
    for w in inv["workflows"]:
        if re.search(r"/home/runner/work/", w["text"]):
            out.append(draft(
                "JQA-CICD-005", w["path"], "Workflow contains runner-specific absolute path",
                "An absolute /home/runner/work/... path is used in the workflow.",
                "Runner/repository naming assumptions can make workflow maintenance and reuse more fragile.",
                "Prefer repository-relative paths or GitHub-provided workspace variables.",
            ))
    return out
