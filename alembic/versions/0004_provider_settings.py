"""Organization model settings and encrypted provider credentials.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
from app.database import Base
from app import models  # noqa: F401

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    models.TenantModelSettings.__table__.create(bind, checkfirst=True)
    models.ProviderCredential.__table__.create(bind, checkfirst=True)


def downgrade():
    op.drop_table("provider_credentials")
    op.drop_table("tenant_model_settings")
