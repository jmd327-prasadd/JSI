from __future__ import annotations

import re
from pathlib import Path

from app.discovery.walker import read_text

DDL_RE = re.compile(
    r"(?i)\bcreate\s+(?:or\s+replace\s+)?(?:transient\s+|temporary\s+)?"
    r"(table|view|procedure|task|stream|pipe|function|stage|sequence)\b"
)
JINJA_RE = re.compile(r"\{\{|\{%")


def is_snowflake_ddl_file(text: str) -> bool:
    """A loose (non-dbt) SQL file that looks like raw Snowflake DDL: has CREATE
    OBJECT statements and no dbt Jinja templating (a dbt model would have both)."""
    return bool(DDL_RE.search(text)) and not JINJA_RE.search(text)


def scan_snowflake_bundle(root: Path, sql_paths: list[Path]) -> dict:
    """Best-effort, regex-only inventory of loose Snowflake SQL scripts.

    This is NOT a real SQL parser -- object/identifier extraction is heuristic
    and always confidence-tagged Medium/Low, matching the same "heuristics
    over a real parser" tradeoff made for dbt discovery (see discovery/dbt.py).
    """
    objects: list[dict] = []
    for path in sql_paths:
        text = read_text(path)
        if not is_snowflake_ddl_file(text):
            continue
        rel = path.relative_to(root).as_posix()
        for m in DDL_RE.finditer(text):
            obj_type = m.group(1).lower()
            # best-effort object name: first identifier after the matched DDL keyword
            tail = text[m.end():m.end() + 200]
            name_m = re.search(r"\s*(?:if\s+not\s+exists\s+)?([A-Za-z0-9_.\"$]+)", tail, re.I)
            name = name_m.group(1) if name_m else "unknown"
            line = text.count("\n", 0, m.start()) + 1
            objects.append({
                "path": rel,
                "object_type": obj_type,
                "object_name": name,
                "line": line,
                "confidence": "Medium",
            })
    return {
        "component_type": "SNOWFLAKE_SQL_BUNDLE",
        "file_count": len({o["path"] for o in objects}),
        "objects": objects,
    }
