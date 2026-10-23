from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CareerGoal, Concept, PreparationTask, Resume, User
from app.schemas import ResumeProfile, ResumeSkill
from app.services.career_planning import build_plan, sync_resume_skills
from app.services.chunking import chunk_pages
from app.services.generation import quote_is_grounded
from app.services.mastery import update_mastery
from app.services.retrieval import reciprocal_rank_fusion


def test_chunks_preserve_page_boundaries():
    chunks = chunk_pages([(3, "Heading\n" + "Sentence about photosynthesis. " * 120)], size=300, overlap=30)
    assert len(chunks) > 1
    assert all(c.page_start == c.page_end == 3 for c in chunks)
    assert "photosynthesis" in chunks[0].text


def test_quote_gate_normalizes_whitespace_and_case():
    assert quote_is_grounded("Water  boils at 100 C.", "WATER boils at 100 C. Under normal pressure.")
    assert not quote_is_grounded("Water freezes at 100 C.", "Water boils at 100 C.")


def test_rrf_rewards_items_present_in_both_rankings():
    scores = reciprocal_rank_fusion([[1, 2, 3], [3, 1, 4]])
    assert scores[1] > scores[2]
    assert scores[3] > scores[4]


def test_mastery_ema():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="test@example.com", password_hash="x")
        db.add(user)
        db.flush()
        concept = Concept(document_id=999, name="Cells", summary="", order_idx=0)
        db.add(concept)
        db.flush()
        row = update_mastery(db, user.id, concept.id, 1.0)
        assert row.score == 0.51
        assert row.attempts_count == 1


def test_career_plan_explains_missing_target_skills():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="career@example.com", password_hash="x")
        db.add(user); db.flush()
        resume = Resume(user_id=user.id, filename="resume.pdf", storage_path="test.pdf", status="ready")
        db.add(resume); db.flush()
        sync_resume_skills(db, user.id, resume, ResumeProfile(skills=[
            ResumeSkill(name="Python", evidence=["Built a Python API"], confidence=0.9)
        ]))
        goal = CareerGoal(
            user_id=user.id, target_role="Backend developer", experience_level="entry",
            job_description="Python, FastAPI, SQL and Docker", interests=["APIs"], weekly_hours=7,
        )
        db.add(goal); db.commit(); db.refresh(goal)
        plan = build_plan(db, user.id, goal)
        assert plan.summary.startswith("Seven-day Backend developer plan")
        tasks = list(db.query(PreparationTask).filter_by(plan_id=plan.id))
        assert tasks
        assert any("Not evidenced" in reason for task in tasks for reason in task.reasons)
