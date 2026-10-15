from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Chunk, Concept, Document, Mastery, Membership, User
from app.schemas import ChunkOut, ConceptOut, DocumentOut
from app.security import current_membership, current_user
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


def owned_document(db: Session, document_id: int, user_id: int) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user_id))
    if not document:
        raise HTTPException(404, "Document not found")
    return document


@router.post("", response_model=DocumentOut, status_code=202)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = None,
    user: User = Depends(current_user),
    membership: Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files are supported")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "PDF is too large")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a valid PDF")
    directory = get_settings().upload_dir / str(user.id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.pdf"
    path.write_bytes(data)
    document = Document(
        user_id=user.id, tenant_id=membership.tenant_id, title=(title or Path(file.filename or "Textbook").stem)[:300],
        filename=(file.filename or "textbook.pdf")[:300], storage_path=str(path),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    background.add_task(ingest_document, document.id)
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return owned_document(db, document_id, user.id)


@router.get("/{document_id}/status", response_model=DocumentOut)
def document_status(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return owned_document(db, document_id, user.id)


@router.get("/{document_id}/file")
def document_file(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = owned_document(db, document_id, user.id)
    return FileResponse(document.storage_path, media_type="application/pdf", filename=document.filename)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = owned_document(db, document_id, user.id)
    storage_path = Path(document.storage_path).resolve()
    upload_root = get_settings().upload_dir.resolve()
    db.delete(document)
    db.commit()
    # Only unlink files within the configured upload directory.
    if storage_path.is_relative_to(upload_root) and storage_path.is_file():
        storage_path.unlink()


@router.get("/{document_id}/concepts", response_model=list[ConceptOut])
def concepts(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_document(db, document_id, user.id)
    rows = list(db.scalars(select(Concept).where(Concept.document_id == document_id).order_by(Concept.order_idx)))
    mastery = {m.concept_id: m.score for m in db.scalars(select(Mastery).where(Mastery.user_id == user.id))}
    return [ConceptOut.model_validate(c).model_copy(update={"mastery": mastery.get(c.id, 0.3)}) for c in rows]


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def chunks(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_document(db, document_id, user.id)
    return list(db.scalars(select(Chunk).where(
        Chunk.document_id == document_id
    ).order_by(Chunk.page_start, Chunk.id)))
