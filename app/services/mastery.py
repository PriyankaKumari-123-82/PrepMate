from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Mastery


def update_mastery(db: Session, user_id: int, concept_id: int, result: float) -> Mastery:
    row = db.get(Mastery, (user_id, concept_id))
    if not row:
        row = Mastery(user_id=user_id, concept_id=concept_id, score=0.3, attempts_count=0)
        db.add(row)
    row.score = max(0.0, min(1.0, 0.7 * row.score + 0.3 * result))
    row.attempts_count += 1
    row.last_seen_at = datetime.now(timezone.utc)
    return row
