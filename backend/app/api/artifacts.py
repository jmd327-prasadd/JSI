from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.artifact import Artifact
from app.models.document import Document
from app.models.project import Project
from app.schemas.artifact import ArtifactOut, DocumentOut
from app.storage import paths as sp

router = APIRouter(prefix="/projects", tags=["artifacts"])

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MiB


@router.post("/{project_id}/artifacts", response_model=ArtifactOut)
async def upload_artifact(project_id: str, file: UploadFile, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported in v1.")

    artifact = Artifact(project_id=project_id, original_filename=file.filename, storage_path="")
    db.add(artifact)
    db.flush()  # assign artifact.id before computing its storage path

    dest = sp.artifact_original_path(project_id, artifact.id, file.filename)
    sp.ensure_parent(dest)

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                db.rollback()
                raise HTTPException(status_code=413, detail="Upload exceeds the 500 MiB limit.")
            out.write(chunk)

    artifact.storage_path = str(dest)
    artifact.size_bytes = size
    db.commit()
    db.refresh(artifact)
    return artifact


@router.post("/{project_id}/documents", response_model=DocumentOut)
async def upload_document(project_id: str, file: UploadFile, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    lower = file.filename.lower()
    if lower.endswith(".pdf"):
        file_type = "pdf"
    elif lower.endswith(".docx"):
        file_type = "docx"
    else:
        raise HTTPException(status_code=400, detail="Only .pdf or .docx uploads are supported.")

    document = Document(project_id=project_id, original_filename=file.filename, file_type=file_type, storage_path="")
    db.add(document)
    db.flush()

    dest = sp.document_original_path(project_id, document.id, file.filename)
    sp.ensure_parent(dest)
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    document.storage_path = str(dest)
    # Conversion to Markdown (pymupdf4llm/markitdown) runs as part of a later
    # build step (documentation ingestion pipeline) -- stays "pending" for now.
    db.commit()
    db.refresh(document)
    return document
