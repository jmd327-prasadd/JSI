from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.analysis_run import AnalysisRun
from app.models.finding import Finding
from app.models.project import Project
from app.reporting.aggregation import summarize
from app.schemas.run import RunOut, RunSummary

router = APIRouter(prefix="/projects", tags=["runs"])


@router.post("/{project_id}/runs", response_model=RunOut)
def create_run(project_id: str, db: Session = Depends(get_db)) -> AnalysisRun:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    run = AnalysisRun(project_id=project_id, status="queued", status_message="Waiting for a worker to pick this up.")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{project_id}/runs", response_model=list[RunOut])
def list_runs(project_id: str, db: Session = Depends(get_db)) -> list[AnalysisRun]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )


def _get_run_or_404(project_id: str, run_id: str, db: Session) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{project_id}/runs/{run_id}", response_model=RunOut)
def get_run(project_id: str, run_id: str, db: Session = Depends(get_db)) -> AnalysisRun:
    return _get_run_or_404(project_id, run_id, db)


@router.get("/{project_id}/runs/{run_id}/inventory")
def get_run_inventory(project_id: str, run_id: str, db: Session = Depends(get_db)):
    run = _get_run_or_404(project_id, run_id, db)
    if not run.inventory_path or not Path(run.inventory_path).exists():
        raise HTTPException(status_code=404, detail="Inventory not available yet for this run.")
    return json.loads(Path(run.inventory_path).read_text(encoding="utf-8"))


@router.get("/{project_id}/runs/{run_id}/read-plan")
def get_run_read_plan(project_id: str, run_id: str, db: Session = Depends(get_db)):
    run = _get_run_or_404(project_id, run_id, db)
    if not run.read_plan_path or not Path(run.read_plan_path).exists():
        raise HTTPException(status_code=404, detail="Read plan not available yet for this run.")
    return json.loads(Path(run.read_plan_path).read_text(encoding="utf-8"))


@router.get("/{project_id}/runs/{run_id}/summary", response_model=RunSummary)
def get_run_summary(project_id: str, run_id: str, db: Session = Depends(get_db)) -> RunSummary:
    run = _get_run_or_404(project_id, run_id, db)
    findings = db.query(Finding).filter(Finding.analysis_run_id == run_id).all()
    agg = summarize(findings)
    return RunSummary(run_id=run_id, status=run.status, **agg)
