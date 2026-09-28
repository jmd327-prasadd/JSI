from __future__ import annotations

from pathlib import Path

from app.discovery.walker import iter_files

HIGH_PRIORITY_READ = "HIGH_PRIORITY_READ"
FULL_BODY_ANALYSIS = "FULL_BODY_ANALYSIS"
METADATA_ONLY = "METADATA_ONLY"

HIGH_PRIORITY_NAMES = {
    "dbt_project.yml", "schema.yml", "source.yml", "sources.yml",
    "manifest.json", "catalog.json", "readme.md", "packages.yml",
}
FULL_BODY_SUFFIXES = {".sql", ".tmdl"}
METADATA_ONLY_SUFFIXES = {".pbix", ".lock"}


def _tier_for(path: Path) -> tuple[str, str]:
    name_lower = path.name.lower()
    suffix = path.suffix.lower()

    if name_lower in HIGH_PRIORITY_NAMES:
        return HIGH_PRIORITY_READ, "signature file for project structure/metadata"
    if suffix in FULL_BODY_SUFFIXES:
        return FULL_BODY_ANALYSIS, "model/measure source requiring rule evaluation"
    if suffix in METADATA_ONLY_SUFFIXES:
        return METADATA_ONLY, "binary or lock file -- not text-analyzable"
    if suffix in {".yml", ".yaml"}:
        return HIGH_PRIORITY_READ, "yaml config, may carry model/source metadata"
    return METADATA_ONLY, "not a recognized code/config artifact type for this build"


def build_read_plan(root: Path) -> list[dict]:
    """Deterministic per-file gate: every file that could ever reach an LLM
    call must appear here first. `llm_eligible` is always False in this build
    (the AI orchestration layer is a later build step) -- FULL_BODY_ANALYSIS
    files are exactly the set a future llm_assisted/hybrid rule is allowed to
    read from, once that layer exists.
    """
    root = root.resolve()
    plan = []
    for path in iter_files(root):
        tier, reason = _tier_for(path)
        rel = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        plan.append({
            "path": rel,
            "tier": tier,
            "reason": reason,
            "bytes": size,
            "llm_eligible": False,
        })
    return plan
