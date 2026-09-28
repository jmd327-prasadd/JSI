from __future__ import annotations

import re
from pathlib import Path

from app.discovery.walker import iter_files, load_yaml, read_text

# NOTE ON APPROACH: this deliberately does NOT run `dbt parse`/`dbt compile` to
# get an authoritative manifest.json/catalog.json. Handover repos are often
# incomplete or broken -- missing adapter config, unresolved package pins --
# which is exactly the case this tool must still work on. Instead it uses the
# same regex/YAML heuristics as the original JQA PoC, which work on any zip
# even if dbt itself couldn't build it. If a manifest.json/catalog.json
# happens to already be in the zip's target/ folder, manifest_enrichment.py
# opportunistically layers authoritative data on top -- enrichment only, never
# required.


def model_context(rel: str) -> tuple[str, str]:
    """Infer (layer, domain) from the dbt path convention models/<layer>/<domain>/..."""
    parts = Path(rel).parts
    layer = domain = ""
    if "models" in parts:
        i = parts.index("models")
        if len(parts) > i + 1:
            layer = parts[i + 1]
        if len(parts) > i + 2:
            domain = parts[i + 2]
    return layer, domain


def discover_dbt_project(root: Path, dbt_project_yml: Path) -> dict:
    """Discover a single dbt project rooted at the directory containing dbt_project_yml.

    Mirrors the original JQA PoC's discovery/core.py + dependencies.py logic
    almost verbatim, generalized to not assume a hardcoded client folder name.
    """
    project_root = dbt_project_yml.parent
    inv: dict = {
        "root": project_root.relative_to(root).as_posix() or ".",
        "dbt_project": load_yaml(dbt_project_yml),
        "dbt_project_path": dbt_project_yml.relative_to(root).as_posix(),
        "files": [], "yaml_files": [],
        "models": [], "models_meta": [], "sources": [],
        "tests": [], "macros": [], "snapshots": [], "workflows": [], "packages": [],
    }

    for path in iter_files(project_root):
        rel = path.relative_to(root).as_posix()
        inv["files"].append(rel)
        suffix = path.suffix.lower()

        if suffix in {".yml", ".yaml"}:
            inv["yaml_files"].append(rel)
            doc = load_yaml(path)
            if path.name == "packages.yml":
                pkgs = doc.get("packages", []) if isinstance(doc, dict) else []
                if pkgs:
                    inv["packages"] = pkgs
            if isinstance(doc, dict):
                for m in doc.get("models", []) or []:
                    if isinstance(m, dict) and m.get("name"):
                        inv["models_meta"].append({
                            "name": str(m["name"]),
                            "description": m.get("description") or "",
                            "tests": m.get("tests") or m.get("data_tests") or [],
                            "columns": m.get("columns") or [],
                            "path": rel,
                        })
                for s in doc.get("sources", []) or []:
                    if isinstance(s, dict) and s.get("name"):
                        inv["sources"].append({
                            "name": str(s["name"]),
                            "description": s.get("description") or "",
                            "freshness": s.get("freshness"),
                            "loaded_at_field": s.get("loaded_at_field"),
                            "tables": s.get("tables") or [],
                            "database": s.get("database", ""),
                            "schema": s.get("schema", ""),
                            "path": rel,
                        })

        if suffix == ".sql":
            text = read_text(path)
            low = text.lower()
            if "/models/" in "/" + rel or rel.startswith("models/"):
                layer, domain = model_context(rel)
                inv["models"].append({
                    "path": rel, "name": path.stem, "layer": layer, "domain": domain,
                    "lines": len(text.splitlines()), "chars": len(text),
                    "select_star": bool(re.search(r"\bselect\s+\*", low)),
                    "hardcoded_relation": bool(re.search(
                        r"\b(from|join)\s+[A-Za-z0-9_$]+\.[A-Za-z0-9_$]+(?:\.[A-Za-z0-9_$]+)?", low
                    )),
                    "joins": len(re.findall(r"\b(?:left|right|full|inner|cross)?\s+join\b", low)),
                    "ctes": len(re.findall(r"\b[A-Za-z0-9_$]+\s+as\s*\(", low)),
                    "is_incremental": "incremental" in low and "{{ config" in low,
                    "has_unique_key": "unique_key" in low,
                    "text": text,
                })
            elif rel.startswith("tests/") or "/tests/" in "/" + rel:
                inv["tests"].append(rel)
            elif rel.startswith("macros/") or "/macros/" in "/" + rel:
                inv["macros"].append(rel)
            elif rel.startswith("snapshots/") or "/snapshots/" in "/" + rel:
                inv["snapshots"].append(rel)

        if rel.startswith(".github/workflows/") or "/.github/workflows/" in "/" + rel:
            inv["workflows"].append({"path": rel, "text": read_text(path)})

    from app.discovery.dependencies import build_dependency_graph
    build_dependency_graph(inv)
    return inv
