from __future__ import annotations

from pathlib import Path

from app.discovery.classifiers import classify, find_loose_snowflake_sql
from app.discovery.dbt import discover_dbt_project
from app.discovery.manifest_enrichment import enrich_with_manifest
from app.discovery.powerbi import scan_powerbi_project, scan_pbix_opaque
from app.discovery.snowflake_sql import scan_snowflake_bundle
from app.discovery.walker import read_text


def _repo_root_workflows(root: Path) -> list[dict]:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.exists():
        return []
    out = []
    for p in wf_dir.rglob("*"):
        if p.is_file():
            out.append({"path": p.relative_to(root).as_posix(), "text": read_text(p)})
    return out


def build_inventory(root: Path) -> dict:
    """Top-level deterministic discovery entry point for one extracted artifact.

    Classifies every discovered file into a component (DBT_PROJECT,
    SNOWFLAKE_SQL_BUNDLE, POWERBI_PROJECT, POWERBI_PBIX_OPAQUE) by signature
    file, then runs the appropriate deep-discovery pass for each.
    """
    root = root.resolve()
    classified = classify(root)
    all_files = classified["all_files"]

    dbt_model_paths: set[Path] = set()
    dbt_projects: list[dict] = []
    for dbt_yml in classified["dbt_projects"]:
        inv = discover_dbt_project(root, dbt_yml)
        enrich_with_manifest(inv, dbt_yml.parent)
        dbt_projects.append(inv)
        dbt_model_paths.update(root / m["path"] for m in inv["models"])

    # Merge repo-root-level CI/CD workflows into every discovered dbt project's
    # inventory (workflows commonly live at the repo root, one level above a
    # dbt project subfolder).
    root_workflows = _repo_root_workflows(root)
    for inv in dbt_projects:
        seen_paths = {w["path"] for w in inv["workflows"]}
        for w in root_workflows:
            if w["path"] not in seen_paths:
                inv["workflows"].append(w)
                seen_paths.add(w["path"])

    loose_sql = find_loose_snowflake_sql(all_files, dbt_model_paths)
    snowflake_bundle = scan_snowflake_bundle(root, loose_sql) if loose_sql else None

    powerbi_projects = [scan_powerbi_project(root, p) for p in classified["powerbi_projects"]]
    pbix_files = [scan_pbix_opaque(root, p) for p in classified["pbix_files"]]

    return {
        "root": str(root),
        "file_count": len(all_files),
        "dbt_projects": dbt_projects,
        "snowflake_bundle": snowflake_bundle,
        "powerbi_projects": powerbi_projects,
        "pbix_files": pbix_files,
    }
