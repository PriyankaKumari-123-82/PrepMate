from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Concept, User
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

