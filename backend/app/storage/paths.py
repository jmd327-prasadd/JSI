from __future__ import annotations

from pathlib import Path

from app.config import settings


def project_dir(project_id: str) -> Path:
    return settings.data_dir / "projects" / project_id


def artifact_dir(project_id: str, artifact_id: str) -> Path:
    return project_dir(project_id) / "artifacts" / artifact_id


def artifact_original_path(project_id: str, artifact_id: str, filename: str) -> Path:
    suffix = Path(filename).suffix or ".zip"
    return artifact_dir(project_id, artifact_id) / f"original{suffix}"


def artifact_extracted_dir(project_id: str, artifact_id: str) -> Path:
    return artifact_dir(project_id, artifact_id) / "extracted"


def document_dir(project_id: str, document_id: str) -> Path:
    return project_dir(project_id) / "documents" / document_id


def document_original_path(project_id: str, document_id: str, filename: str) -> Path:
    suffix = Path(filename).suffix or ".bin"
    return document_dir(project_id, document_id) / f"original{suffix}"


def document_converted_path(project_id: str, document_id: str) -> Path:
    return document_dir(project_id, document_id) / "converted.md"


def run_dir(project_id: str, run_id: str) -> Path:
    return project_dir(project_id) / "runs" / run_id


def run_inventory_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / "inventory.json"


def run_read_plan_path(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / "read_plan.json"


def run_llm_calls_dir(project_id: str, run_id: str) -> Path:
    return run_dir(project_id, run_id) / "llm_calls"


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
