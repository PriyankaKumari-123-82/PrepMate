from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attempt, AttemptAnswer, Concept, Mastery, User
from app.security import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.execute(
        select(Mastery, Concept).join(Concept, Concept.id == Mastery.concept_id)
        .where(Mastery.user_id == user.id).order_by(Mastery.score)
    ))
    total = db.scalar(select(func.count()).select_from(AttemptAnswer).join(Attempt).where(Attempt.user_id == user.id)) or 0
    correct = db.scalar(select(func.count()).select_from(AttemptAnswer).join(Attempt).where(
        Attempt.user_id == user.id, AttemptAnswer.correct.is_(True)
    )) or 0
    return {
        "accuracy": correct / total if total else 0,
        "answers": total,
        "weak_concepts": [{"id": c.id, "name": c.name, "score": m.score} for m, c in rows[:5]],
        "study_next": rows[0][1].name if rows else None,
    }
