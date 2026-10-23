"""Student resume and career preparation domain.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

from app import models

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (
        models.Resume.__table__, models.CareerGoal.__table__, models.Skill.__table__,
        models.StudentSkill.__table__, models.PreparationPlan.__table__,
        models.PreparationTask.__table__,
    ):
        table.create(bind, checkfirst=True)


def downgrade():
    for name in (
        "preparation_tasks", "preparation_plans", "student_skills",
        "skills", "career_goals", "resumes",
    ):
        op.drop_table(name)
