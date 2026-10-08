import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.documents import owned_document
from app.database import get_db
from app.models import Attempt, AttemptAnswer, Concept, Mastery, Question, User
from app.schemas import AnswerFeedback, AnswerIn, AttemptOut, PublicQuestion, TestCreate
from app.security import current_user
from app.services.mastery import update_mastery

router = APIRouter(tags=["practice"])


@router.post("/tests", response_model=AttemptOut, status_code=201)
def create_test(payload: TestCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for document_id in payload.document_ids:
        document = owned_document(db, document_id, user.id)
        if document.status != "ready":
            raise HTTPException(409, f"Document {document_id} is not ready")
    questions = list(db.scalars(select(Question).where(
        Question.document_id.in_(payload.document_ids), Question.active.is_(True)
    )))
    if not questions:
        raise HTTPException(409, "No questions have been generated for these documents")
    mastery = {m.concept_id: m.score for m in db.scalars(select(Mastery).where(Mastery.user_id == user.id))}
    # Weak concepts sort first; random tie breaker avoids a fixed repeated test.
    random.shuffle(questions)
    questions.sort(key=lambda q: mastery.get(q.concept_id, 0.3))
    chosen = questions[:payload.count]
    attempt = Attempt(user_id=user.id, mode=payload.mode, document_ids=payload.document_ids)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return AttemptOut(id=attempt.id, mode=attempt.mode, questions=[PublicQuestion.model_validate(q) for q in chosen])


def _grade(question: Question, response: str) -> tuple[bool, float]:
    expected = set(question.answer.casefold().split())
    actual = set(response.casefold().split())
    overlap = len(expected & actual) / max(1, len(expected))
    correct = response.strip().casefold() == question.answer.strip().casefold() if question.type == "mcq" else overlap >= 0.45
    return correct, 1.0 if correct else 0.0


@router.post("/attempts/{attempt_id}/answers", response_model=AnswerFeedback)
def submit_answer(attempt_id: int, payload: AnswerIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    if attempt.submitted_at:
        raise HTTPException(409, "Attempt is already submitted")
    question = db.get(Question, payload.question_id)
    if not question or question.document_id not in attempt.document_ids:
        raise HTTPException(400, "Question is not part of this attempt")
    if db.scalar(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.question_id == question.id)):
        raise HTTPException(409, "Question was already answered")
    correct, marks = _grade(question, payload.response)
    db.add(AttemptAnswer(
        attempt_id=attempt.id, question_id=question.id, response=payload.response,
        correct=correct, marks=marks, feedback=question.explanation, time_taken_s=payload.time_taken_s,
    ))
    if attempt.mode == "practice":
        update_mastery(db, user.id, question.concept_id, marks)
    db.commit()
    return AnswerFeedback(
        correct=correct, marks=marks, answer=question.answer, explanation=question.explanation,
        source_quote=question.source_quote, page=question.page,
    )


@router.post("/attempts/{attempt_id}/submit")
def finish_attempt(attempt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    answers = list(db.scalars(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)))
    if attempt.mode == "mock":
        for answer in answers:
            question = db.get(Question, answer.question_id)
            update_mastery(db, user.id, question.concept_id, answer.marks / answer.max_marks)
    attempt.score = sum(a.marks for a in answers) / max(1, sum(a.max_marks for a in answers))
    attempt.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": attempt.id, "score": attempt.score, "answered": len(answers)}


@router.post("/questions/{question_id}/flag")
def flag(question_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Question not found")
    owned_document(db, question.document_id, user.id)
    question.flag_count += 1
    if question.flag_count >= 3:
        question.active = False
    db.commit()
    return {"flag_count": question.flag_count, "active": question.active}
