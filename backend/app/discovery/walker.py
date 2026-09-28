from __future__ import annotations

from pathlib import Path

import yaml

# Directories never worth walking into for any artifact type: VCS internals,
# dbt/JS build+dependency output, and Python/virtualenv noise.
SKIP = {
    ".git", "target", "logs", "__pycache__", "dbt_packages",
    ".venv", "venv", "node_modules", ".next", "dist", "build", ".terraform",
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def load_yaml(path: Path):
    try:
        return yaml.safe_load(read_text(path)) or {}
    except Exception:
        return {}


def iter_files(root: Path):
    """Yield every file under root that isn't inside a SKIP directory."""
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        yield path
