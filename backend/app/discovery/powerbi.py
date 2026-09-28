from __future__ import annotations

import re
from pathlib import Path

from app.discovery.walker import read_text

# TMDL (Tabular Model Definition Language) is the plain-text format used by
# Power BI Desktop's newer .pbip project layout (*.SemanticModel/definition/*.tmdl).
# A .pbix file is a binary/zip container -- not text-parseable without extra
# tooling, so it is recorded as opaque metadata only (see classifiers.py).
TABLE_RE = re.compile(r"(?im)^table\s+(\S+)")
MEASURE_RE = re.compile(r"(?im)^\s*measure\s+(\S+)\s*=")
RELATIONSHIP_RE = re.compile(r"(?im)^relationship\s+(\S+)")


def scan_powerbi_project(root: Path, pbip_path: Path) -> dict:
    project_root = pbip_path.parent
    tmdl_files = list(project_root.rglob("*.tmdl"))
    tables: list[dict] = []
    measures: list[dict] = []
    relationships: list[dict] = []

    for path in tmdl_files:
        text = read_text(path)
        rel = path.relative_to(root).as_posix()
        for m in TABLE_RE.finditer(text):
            tables.append({"name": m.group(1), "path": rel})
        for m in MEASURE_RE.finditer(text):
            measures.append({"name": m.group(1), "path": rel})
        for m in RELATIONSHIP_RE.finditer(text):
            relationships.append({"name": m.group(1), "path": rel})

    return {
        "component_type": "POWERBI_PROJECT",
        "pbip_path": pbip_path.relative_to(root).as_posix(),
        "tmdl_file_count": len(tmdl_files),
        "tables": tables,
        "measures": measures,
        "relationships": relationships,
        "confidence": "Medium",
    }


def scan_pbix_opaque(root: Path, pbix_path: Path) -> dict:
    return {
        "component_type": "POWERBI_PBIX_OPAQUE",
        "path": pbix_path.relative_to(root).as_posix(),
        "size_bytes": pbix_path.stat().st_size,
        "note": "Binary Power BI file -- not text-parseable. Recorded as present; deep analysis skipped for v1.",
        "confidence": "Low",
    }
