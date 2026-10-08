import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services.llm import llm


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document_title: str
    score: float


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, 1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    denominator = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0


async def retrieve(db: Session, query: str, document_ids: list[int], k: int = 4) -> list[RetrievedChunk]:
    """Access-scoped hybrid RAG retrieval using dense + keyword RRF."""
    chunks = list(db.scalars(select(Chunk).where(Chunk.document_id.in_(document_ids))))
    if not chunks:
        return []
    query_embedding = (await llm.embed([query]))[0]
    dense = sorted(chunks, key=lambda c: _cosine(query_embedding, c.embedding or []), reverse=True)
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    keyword = sorted(chunks, key=lambda c: len(terms & set(re.findall(r"[a-z0-9]+", c.text.lower()))), reverse=True)
    scores = reciprocal_rank_fusion([[c.id for c in dense], [c.id for c in keyword]])
    docs = {d.id: d.title for d in db.scalars(select(Document).where(Document.id.in_(document_ids)))}
    ranked = sorted(chunks, key=lambda c: scores.get(c.id, 0), reverse=True)[:k]
    return [RetrievedChunk(c, docs.get(c.document_id, "Textbook"), scores[c.id]) for c in ranked]
