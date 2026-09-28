from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.discovery.inventory import build_inventory
from app.models.analysis_run import AnalysisRun
from app.models.artifact import Artifact
from app.models.finding import Finding
from app.pipeline.read_plan import build_read_plan
from app.rules.evaluate import draft_to_finding_kwargs, evaluate_inventory
from app.storage import paths as sp
from app.storage.zip_extract import clear_dir, safe_extract, sha256_of

log = logging.getLogger(__name__)


def _set_stage(db: Session, run: AnalysisRun, status: str, progress: int, message: str) -> None:
    run.status = status
    run.progress_pct = progress
    run.status_message = message
    db.commit()


def run_pipeline(db: Session, run: AnalysisRun) -> None:
    """Executes one analysis run's pipeline stages against its project's
    current artifacts. A single failed stage marks the run 'failed' with
    error_message set and does not raise -- the worker loop keeps polling
    for the next queued run regardless.
    """
    try:
        artifacts = list(db.query(Artifact).filter(Artifact.project_id == run.project_id).all())
        if not artifacts:
            _set_stage(db, run, "failed", 0, "No code artifacts uploaded for this project.")
            run.error_message = "No artifacts to analyze."
            db.commit()
            return

        _set_stage(db, run, "extracting", 10, f"Extracting {len(artifacts)} artifact(s).")
        for artifact in artifacts:
            extracted_dir = sp.artifact_extracted_dir(run.project_id, artifact.id)
            zip_path = Path(artifact.storage_path)
            artifact.extraction_status = "extracting"
            db.commit()
            safe_extract(zip_path, extracted_dir)
            artifact.sha256 = artifact.sha256 or sha256_of(zip_path)
            artifact.extraction_status = "extracted"
            db.commit()

        _set_stage(db, run, "discovering", 30, "Classifying and discovering project structure.")
        run_dir = sp.run_dir(run.project_id, run.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        inventories: dict[str, dict] = {}
        read_plans: dict[str, list[dict]] = {}
        for artifact in artifacts:
            extracted_dir = sp.artifact_extracted_dir(run.project_id, artifact.id)
            inv = build_inventory(extracted_dir)
            inventories[artifact.id] = inv
            read_plans[artifact.id] = build_read_plan(extracted_dir)
            artifact.inventory_summary = {
                "file_count": inv["file_count"],
                "dbt_project_count": len(inv["dbt_projects"]),
                "has_snowflake_bundle": inv["snowflake_bundle"] is not None,
                "powerbi_project_count": len(inv["powerbi_projects"]),
                "pbix_file_count": len(inv["pbix_files"]),
            }
            db.commit()

        inventory_path = sp.run_inventory_path(run.project_id, run.id)
        sp.ensure_parent(inventory_path).write_text(
            json.dumps(
                {aid: _strip_sql_text(inv) for aid, inv in inventories.items()},
                indent=2, default=str,
            ),
            encoding="utf-8",
        )
        run.inventory_path = str(inventory_path)

        read_plan_path = sp.run_read_plan_path(run.project_id, run.id)
        sp.ensure_parent(read_plan_path).write_text(
            json.dumps(read_plans, indent=2), encoding="utf-8",
        )
        run.read_plan_path = str(read_plan_path)
        db.commit()

        _set_stage(db, run, "evaluating_rules", 60, "Running deterministic rule checks.")
        for artifact in artifacts:
            extracted_dir = sp.artifact_extracted_dir(run.project_id, artifact.id)
            drafts = evaluate_inventory(inventories[artifact.id], extracted_dir)
            for d in drafts:
                kwargs = draft_to_finding_kwargs(d)
                kwargs["source_ref"] = {"artifact_id": artifact.id, "file_path": d.component}
                db.add(Finding(analysis_run_id=run.id, project_id=run.project_id, **kwargs))
            db.commit()

        # AI judgment layer is a later build step -- llm_assisted/hybrid rules
        # currently produce no findings beyond their deterministic baseline.
        _set_stage(db, run, "llm_judgment", 80, "AI judgment layer not yet enabled for this build.")

        _set_stage(db, run, "aggregating", 95, "Aggregating results.")

        run.status = "done"
        run.progress_pct = 100
        run.status_message = "Analysis complete."
        run.finished_at = dt.datetime.utcnow()
        db.commit()

        # Best-effort disk cleanup only -- re-extracted fresh on the next run
        # regardless. Must NOT be able to turn an already-successful run into
        # a failed one, so failures here are logged and swallowed, never
        # raised into the outer handler below.
        for artifact in artifacts:
            try:
                clear_dir(sp.artifact_extracted_dir(run.project_id, artifact.id))
            except OSError:
                log.warning(
                    "post-run cleanup failed for artifact %s (run %s) -- leaving "
                    "extracted/ in place, will be overwritten on next re-extract",
                    artifact.id, run.id, exc_info=True,
                )

    except Exception as exc:  # noqa: BLE001 -- a failed run must not crash the worker loop
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = dt.datetime.utcnow()
        db.commit()


def _strip_sql_text(inv: dict) -> dict:
    """Drop full SQL bodies before persisting inventory.json -- they're already
    in the extracted/ tree while a run's data lives, and keeping them out of
    the JSON summary keeps it small and readable for the "what did JQA look
    at" audit view.
    """
    slim = dict(inv)
    slim["dbt_projects"] = [
        {**p, "models": [{k: v for k, v in m.items() if k != "text"} for m in p["models"]]}
        for p in inv.get("dbt_projects", [])
    ]
    return slim
