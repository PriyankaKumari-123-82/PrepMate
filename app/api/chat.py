from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.documents import owned_document
from app.database import get_db
from app.models import ChatMessage, User
from app.schemas import ChatIn, ChatOut, Citation
from app.security import current_user
from app.services.llm import llm
from app.services.retrieval import retrieve

router = APIRouter(prefix="/chat", tags=["rag"])


@router.post("", response_model=ChatOut)
async def chat(payload: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for document_id in payload.document_ids:
        owned_document(db, document_id, user.id)  # hard access-control boundary
    results = await retrieve(db, payload.message, payload.document_ids, payload.k)
    if not results:
        answer, citations = "The selected textbook material does not cover this question.", []
    else:
        context = "\n\n".join(f"[{i}] Page {r.chunk.page_start}: {r.chunk.text}" for i, r in enumerate(results, 1))
        answer = await llm.answer(payload.message, context)
        citations = [Citation(
            document_id=r.chunk.document_id, document_title=r.document_title,
            page=r.chunk.page_start, quote=r.chunk.text[:500], score=r.score,
        ) for r in results]
    db.add(ChatMessage(user_id=user.id, role="user", content=payload.message))
    db.add(ChatMessage(user_id=user.id, role="assistant", content=answer, citations=[c.model_dump() for c in citations]))
    db.commit()
    return ChatOut(answer=answer, citations=citations)

