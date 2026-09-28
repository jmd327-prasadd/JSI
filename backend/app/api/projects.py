from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.connection import Connection
from app.models.project import Project
from app.schemas.artifact import ArtifactOut, DocumentOut
from app.schemas.project import ConnectionCreate, ConnectionOut, ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(name=body.name, client_name=body.client_name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).order_by(Project.created_at.desc()).all()


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    return _get_project_or_404(project_id, db)


@router.get("/{project_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(project_id: str, db: Session = Depends(get_db)):
    _get_project_or_404(project_id, db)
    return db.get(Project, project_id).artifacts


@router.get("/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(project_id: str, db: Session = Depends(get_db)):
    _get_project_or_404(project_id, db)
    return db.get(Project, project_id).documents


@router.post("/{project_id}/connections", response_model=ConnectionOut)
def create_connection_stub(project_id: str, body: ConnectionCreate, db: Session = Depends(get_db)) -> Connection:
    """Stub only -- Environment/connections analysis is deferred per v1 scope.
    This just records intent so the UI's "Connections" tab has something to show.
    """
    _get_project_or_404(project_id, db)
    conn = Connection(project_id=project_id, connector_type=body.connector_type, status="not_configured")
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/{project_id}/connections", response_model=list[ConnectionOut])
def list_connections(project_id: str, db: Session = Depends(get_db)):
    _get_project_or_404(project_id, db)
    return db.get(Project, project_id).connections
