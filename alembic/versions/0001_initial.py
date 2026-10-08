"""Initial PrepMate schema.

Revision ID: 0001
"""
from alembic import op
from app.database import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED")
        op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING gin(tsv)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")

def downgrade():
    Base.metadata.drop_all(op.get_bind())
