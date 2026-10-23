from pathlib import Path

import pymupdf

from app.config import get_settings
from app.database import SessionLocal
from app.models import Chunk, Document, Page
from app.services.chunking import chunk_pages
from app.services.generation import generate_bank
from app.services.llm import llm
from app.services.storage import read_pdf


async def ingest_document(document_id: int) -> None:
    """Background-safe ingestion: each job owns its database session."""
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if not document:
            return
        try:
            document.status, document.progress = "extracting", 10
            db.commit()
            pdf = pymupdf.open(stream=read_pdf(document.storage_path), filetype="pdf")
            if len(pdf) > get_settings().max_pdf_pages:
                raise ValueError(f"PDF exceeds {get_settings().max_pdf_pages} page limit")
            extracted: list[tuple[int, str]] = []
            for number, page in enumerate(pdf, 1):
                text = page.get_text("text").strip()
                # OCR is intentionally a deployment extension; record text-poor pages accurately.
                db.add(Page(document_id=document.id, page_no=number, text=text, is_ocr=False))
                extracted.append((number, text))
            document.page_count = len(pdf)
            document.status, document.progress = "indexing", 45
            db.commit()

            pieces = chunk_pages(extracted)
            embeddings = await llm.embed([piece.text for piece in pieces]) if pieces else []
            for piece, embedding in zip(pieces, embeddings):
                db.add(Chunk(
                    document_id=document.id, page_start=piece.page_start, page_end=piece.page_end,
                    section=piece.section, text=piece.text, embedding=embedding,
                ))
            document.status, document.progress = "generating", 75
            db.commit()
            generate_bank(db, document.id)
            document.status, document.progress, document.error = "ready", 100, None
            db.commit()
        except Exception as exc:
            db.rollback()
            document = db.get(Document, document_id)
            if document:
                document.status, document.error = "failed", str(exc)
                db.commit()
