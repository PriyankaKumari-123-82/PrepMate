from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AgentRun, AgentStep, Artifact, User
from app.schemas import GenerateArtifactIn
from app.services.retrieval import RetrievedChunk, retrieve


def _source(result: RetrievedChunk) -> dict[str, Any]:
    return {
        "kind": "document",
        "document_id": result.chunk.document_id,
        "page": result.chunk.page_start,
        "chunk_id": result.chunk.id,
        "quote": result.chunk.text[:500],
    }


def _draft(payload: GenerateArtifactIn, evidence: list[RetrievedChunk]) -> dict[str, Any]:
    snippets = [row.chunk.text[:420].strip() for row in evidence]
    if payload.artifact_type == "assessment":
        count = min(20, max(1, int(payload.constraints.get("question_count", 5))))
        marks = max(1, int(payload.constraints.get("marks_per_question", 2)))
        questions = []
        for index in range(count):
            row = evidence[index % len(evidence)]
            quote = row.chunk.text[:420].strip()
            questions.append({
                "position": index + 1,
                "type": "short",
                "stem": f"Explain the key idea in the supplied material about {payload.topic} (item {index + 1}).",
                "answer_key": quote,
                "marks": marks,
                "difficulty": payload.constraints.get("difficulty", "medium"),
                "bloom_level": payload.constraints.get("bloom_level", "understand"),
                "source_chunk_id": row.chunk.id,
                "source_page": row.chunk.page_start,
            })
        return {"topic": payload.topic, "total_marks": count * marks, "questions": questions}
    if payload.artifact_type == "course_plan":
        weeks = min(52, max(1, int(payload.constraints.get("weeks", 12))))
        return {"topic": payload.topic, "weeks": [
            {"week": i + 1, "focus": snippets[i % len(snippets)][:180], "activity": "Teach, discuss, and check understanding"}
            for i in range(weeks)
        ]}
    sections = [{"heading": f"{payload.topic}: source {i + 1}", "content": text} for i, text in enumerate(snippets)]
    return {
        "topic": payload.topic,
        "format": payload.artifact_type,
        "objectives": [f"Explain the core ideas of {payload.topic}", f"Apply evidence from the supplied texts"],
        "sections": sections,
        "activities": ["Retrieval warm-up", "Guided source analysis", "Exit check"],
    }


async def generate_artifact(db: Session, tenant_id: int, user: User, payload: GenerateArtifactIn) -> tuple[AgentRun, Artifact]:
    run = AgentRun(tenant_id=tenant_id, user_id=user.id, workflow=payload.artifact_type, input=payload.model_dump())
    db.add(run)
    db.flush()
    try:
        evidence = await retrieve(db, payload.topic, payload.document_ids, k=min(8, max(3, len(payload.document_ids) * 2)))
        if not evidence:
            raise ValueError("No indexed evidence was found in the selected documents")
        db.add(AgentStep(run_id=run.id, agent="knowledge", input={"query": payload.topic}, output={"chunk_ids": [r.chunk.id for r in evidence]}))
        body = _draft(payload, evidence)
        sources = [_source(row) for row in evidence]
        db.add(AgentStep(run_id=run.id, agent=payload.artifact_type, input=payload.constraints, output=body))
        warnings = [] if sources else ["No sources were attached"]
        review = {"grounded": bool(sources), "source_count": len(sources), "issues": warnings}
        db.add(AgentStep(run_id=run.id, agent="review", input={"artifact_type": payload.artifact_type}, output=review))
        artifact = Artifact(
            tenant_id=tenant_id, owner_id=user.id, course_id=payload.course_id, run_id=run.id,
            artifact_type=payload.artifact_type, title=payload.title, body=body, sources=sources, warnings=warnings,
        )
        db.add(artifact)
        db.flush()
        run.status = "completed"
        run.output = {"artifact_id": artifact.id, "review": review}
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(artifact)
        return run, artifact
    except Exception as exc:
        run.status, run.error, run.completed_at = "failed", str(exc), datetime.now(timezone.utc)
        db.commit()
        raise
