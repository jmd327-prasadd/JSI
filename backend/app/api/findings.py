from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.analysis_run import AnalysisRun
from app.models.finding import Finding
from app.schemas.finding import FindingOut, FindingStatusUpdate

router = APIRouter(prefix="/projects", tags=["findings"])

VALID_STATUSES = {"New", "Acknowledged", "Needs Dev Fix", "False Positive", "Won't Fix"}


@router.get("/{project_id}/runs/{run_id}/findings", response_model=list[FindingOut])
def list_findings(
    project_id: str,
    run_id: str,
    severity: str | None = Query(default=None),
    category: str | None = Query(default=None),
    detection_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")

    q = db.query(Finding).filter(Finding.analysis_run_id == run_id)
    if severity:
        q = q.filter(Finding.severity == severity)
    if category:
        q = q.filter(Finding.category == category)
    if detection_type:
        q = q.filter(Finding.detection_type == detection_type)
    if status:
        q = q.filter(Finding.status == status)
    return q.order_by(Finding.created_at.asc()).all()


@router.patch("/{project_id}/findings/{finding_id}", response_model=FindingOut)
def update_finding_status(project_id: str, finding_id: str, body: FindingStatusUpdate, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    finding.status = body.status
    finding.reviewer_note = body.reviewer_note
    db.commit()
    db.refresh(finding)
    return finding
