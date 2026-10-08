import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Chunk, Concept, Question


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def quote_is_grounded(quote: str, context: str) -> bool:
    return bool(quote.strip()) and normalize(quote) in normalize(context)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 45 <= len(s.strip()) <= 350]


def generate_bank(db: Session, document_id: int) -> int:
    """Grounded offline generator. An LLM generator can replace this behind the same gate."""
    chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.id)))
    db.execute(delete(Question).where(Question.document_id == document_id))
    db.execute(delete(Concept).where(Concept.document_id == document_id))
    concepts: list[Concept] = []
    seen: set[str] = set()
    for chunk in chunks:
        name = (chunk.section or "Key ideas").strip()[:250]
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        summary = " ".join(_sentences(chunk.text)[:2]) or chunk.text[:400]
        concept = Concept(document_id=document_id, name=name, summary=summary, order_idx=len(concepts))
        db.add(concept)
        db.flush()
        concepts.append(concept)
        if len(concepts) >= 25:
            break
    if not concepts and chunks:
        concept = Concept(document_id=document_id, name="Chapter overview", summary=chunks[0].text[:400], order_idx=0)
        db.add(concept)
        db.flush()
        concepts.append(concept)

    count = 0
    for index, chunk in enumerate(chunks):
        sentences = _sentences(chunk.text)
        if not sentences or not concepts:
            continue
        quote = sentences[0]
        if not quote_is_grounded(quote, chunk.text):
            continue
        concept = concepts[index % len(concepts)]
        # Short answers are useful without fabricated distractors and remain fully grounded.
        db.add(Question(
            document_id=document_id,
            concept_id=concept.id,
            type="short",
            stem=f"Explain this idea from {concept.name}: {quote[:90]}…",
            options=None,
            answer=quote,
            explanation=f"A complete answer should include: {quote}",
            page=chunk.page_start,
            source_quote=quote,
            chunk_ids=[chunk.id],
            difficulty="medium",
        ))
        count += 1
    db.commit()
    return count

