from __future__ import annotations

import json
from pathlib import Path


def find_manifest_files(project_root: Path) -> dict[str, Path]:
    found = {}
    for name in ("manifest.json", "catalog.json"):
        candidates = list((project_root / "target").glob(name)) if (project_root / "target").exists() else []
        if candidates:
            found[name.split(".")[0]] = candidates[0]
    return found


def enrich_with_manifest(inv: dict, project_root: Path) -> None:
    """Opportunistic, never-required enrichment: if a compiled manifest.json
    happens to already be included in the zip's target/ folder, layer its
    authoritative materialization/test data onto the regex-derived model
    records. Silently does nothing if absent or unparseable.
    """
    manifests = find_manifest_files(project_root)
    manifest_path = manifests.get("manifest")
    if not manifest_path:
        return
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return

    nodes = data.get("nodes", {}) if isinstance(data, dict) else {}
    by_name = {}
    for node in nodes.values():
        if isinstance(node, dict) and node.get("resource_type") == "model":
            by_name[node.get("name")] = node

    for m in inv.get("models", []):
        node = by_name.get(m["name"])
        if not node:
            continue
        config = node.get("config", {}) or {}
        m["manifest_materialized"] = config.get("materialized", "")
        m["manifest_unique_key"] = config.get("unique_key")
        m["manifest_enriched"] = True
