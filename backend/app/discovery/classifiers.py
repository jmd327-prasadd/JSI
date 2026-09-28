from __future__ import annotations

from pathlib import Path

from app.discovery.walker import iter_files
from app.discovery.snowflake_sql import is_snowflake_ddl_file
from app.discovery.walker import read_text


def find_dbt_projects(root: Path, all_files: list[Path]) -> list[Path]:
    return [p for p in all_files if p.name == "dbt_project.yml"]


def find_powerbi_projects(root: Path, all_files: list[Path]) -> list[Path]:
    return [p for p in all_files if p.suffix.lower() == ".pbip"]


def find_pbix_files(root: Path, all_files: list[Path]) -> list[Path]:
    return [p for p in all_files if p.suffix.lower() == ".pbix"]


def find_loose_snowflake_sql(all_files: list[Path], dbt_model_paths: set[Path]) -> list[Path]:
    """.sql files that are Snowflake DDL and not already claimed by a dbt project's models/."""
    out = []
    for p in all_files:
        if p.suffix.lower() != ".sql" or p in dbt_model_paths:
            continue
        if is_snowflake_ddl_file(read_text(p)):
            out.append(p)
    return out


def classify(root: Path) -> dict:
    all_files = list(iter_files(root))
    return {
        "all_files": all_files,
        "dbt_projects": find_dbt_projects(root, all_files),
        "powerbi_projects": find_powerbi_projects(root, all_files),
        "pbix_files": find_pbix_files(root, all_files),
    }
