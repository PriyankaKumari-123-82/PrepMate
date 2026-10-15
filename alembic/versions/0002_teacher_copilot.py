"""Teacher copilot domain and tenancy.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from sqlalchemy import inspect

from app.database import Base
from app import models  # noqa: F401

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    # create_all safely adds the new domain tables while leaving v1 data intact.
    Base.metadata.create_all(bind)
    document_columns = {c["name"] for c in inspect(bind).get_columns("documents")}
    if "tenant_id" not in document_columns:
        op.add_column("documents", models.Document.__table__.c.tenant_id.copy())
    if "subject_id" not in document_columns:
        op.add_column("documents", models.Document.__table__.c.subject_id.copy())
    # Preserve v1 accounts by provisioning one isolated institution per user.
    op.execute("""
        INSERT INTO tenants (name, slug, created_at)
        SELECT u.email || ' institution', 'legacy-user-' || CAST(u.id AS VARCHAR), CURRENT_TIMESTAMP
        FROM users u
        WHERE NOT EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = u.id)
    """)
    op.execute("""
        INSERT INTO memberships (tenant_id, user_id, role)
        SELECT t.id, u.id, 'admin'
        FROM users u JOIN tenants t ON t.slug = 'legacy-user-' || CAST(u.id AS VARCHAR)
        WHERE NOT EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = u.id)
    """)
    op.execute("""
        UPDATE documents d SET tenant_id = m.tenant_id
        FROM memberships m WHERE d.user_id = m.user_id AND d.tenant_id IS NULL
    """)


def downgrade():
    op.drop_column("documents", "subject_id")
    op.drop_column("documents", "tenant_id")
    for name in ["approvals", "reviews", "artifacts", "agent_steps", "agent_runs", "learning_outcomes", "units", "courses", "subjects", "memberships", "tenants"]:
        op.drop_table(name)
