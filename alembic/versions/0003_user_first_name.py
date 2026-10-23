"""Add user first name.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    user_columns = {column["name"] for column in inspect(bind).get_columns("users")}
    if "first_name" not in user_columns:
        op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))


def downgrade():
    bind = op.get_bind()
    user_columns = {column["name"] for column in inspect(bind).get_columns("users")}
    if "first_name" in user_columns:
        op.drop_column("users", "first_name")
