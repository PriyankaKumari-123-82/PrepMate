from datetime import date, timedelta
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CareerGoal, PreparationPlan, PreparationTask, Resume, Skill, StudentSkill
from app.schemas import ResumeProfile
from app.services.resume_parser import SKILL_ALIASES


ROLE_SKILLS = {
    "software": ["Data Structures", "Git", "SQL", "Communication"],
    "frontend": ["JavaScript", "TypeScript", "React", "Git", "Communication"],
    "backend": ["Python", "FastAPI", "SQL", "Git", "Docker"],
    "data": ["Python", "SQL", "Machine Learning", "Communication"],
    "machine learning": ["Python", "Machine Learning", "SQL", "Data Structures"],
}


def _canonical(name: str) -> tuple[str, str, list[str]]:
    lowered = name.strip().casefold()
    for canonical, aliases in SKILL_ALIASES.items():
        if lowered == canonical.casefold() or lowered in aliases:
            category = "soft" if canonical == "Communication" else "technical"
            return canonical, category, aliases
    return name.strip()[:120].title(), "general", [lowered]


def get_or_create_skill(db: Session, name: str) -> Skill:
    canonical, category, aliases = _canonical(name)
    skill = db.scalar(select(Skill).where(func.lower(Skill.canonical_name) == canonical.casefold()))
    if not skill:
        skill = Skill(canonical_name=canonical, category=category, aliases=aliases)
        db.add(skill)
        db.flush()
    return skill


def sync_resume_skills(db: Session, user_id: int, resume: Resume, profile: ResumeProfile) -> None:
    for item in profile.skills:
        skill = get_or_create_skill(db, item.name)
        row = db.scalar(select(StudentSkill).where(
            StudentSkill.user_id == user_id, StudentSkill.skill_id == skill.id
        ))
        if not row:
            row = StudentSkill(user_id=user_id, skill_id=skill.id)
            db.add(row)
        row.resume_id = resume.id
        row.claimed_level = row.claimed_level if row.claimed_level is not None else 0.5
        row.confidence = item.confidence
        row.evidence = item.evidence
        row.confirmed = True


def build_plan(db: Session, user_id: int, goal: CareerGoal) -> PreparationPlan:
    target_text = f"{goal.target_role} {goal.job_description or ''}".casefold()
    names: dict[str, tuple[float, list[str]]] = {}
    for role_key, role_skills in ROLE_SKILLS.items():
        if role_key in target_text:
            for name in role_skills:
                names[name] = (0.8, ["Core skill for the target role"])
    for name, aliases in SKILL_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", target_text) for alias in aliases):
            names[name] = (1.0, ["Explicitly required by the target role or job description"])
    if not names:
        names = {
            "Communication": (0.8, ["Common interview requirement"]),
            "Data Structures": (0.7, ["General technical interview foundation"]),
            "Git": (0.6, ["General software delivery foundation"]),
        }

    current = {
        skill.canonical_name: (student, skill)
        for student, skill in db.execute(
            select(StudentSkill, Skill).join(Skill, Skill.id == StudentSkill.skill_id)
            .where(StudentSkill.user_id == user_id)
        )
    }
    interests = {item.casefold() for item in goal.interests}
    ranked = []
    for name, (importance, base_reasons) in names.items():
        skill = get_or_create_skill(db, name)
        student = current.get(skill.canonical_name, (None, skill))[0]
        claimed = student.claimed_level if student and student.claimed_level is not None else 0.0
        assessed = student.assessed_level if student and student.assessed_level is not None else 0.0
        assessed_gap = 1.0 - max(claimed * 0.5, assessed)
        mastery_weakness = 1.0 - assessed if student and student.assessed_level is not None else 0.5
        interest = 1.0 if skill.canonical_name.casefold() in interests else 0.5
        priority = round(0.35 * importance + 0.25 * assessed_gap + 0.20 * assessed_gap + 0.10 * mastery_weakness + 0.10 * interest, 3)
        reasons = list(base_reasons)
        if not student or not student.evidence:
            reasons.append("Not evidenced in the confirmed resume")
        if not student or student.assessed_level is None:
            reasons.append("Needs a diagnostic assessment")
        if interest == 1.0:
            reasons.append("Matches a stated interest")
        if student:
            student.target_level = importance
        ranked.append((priority, skill, reasons))

    previous = list(db.scalars(select(PreparationPlan).where(
        PreparationPlan.user_id == user_id, PreparationPlan.status == "active"
    )))
    for row in previous:
        row.status = "superseded"
    version = (db.scalar(select(func.max(PreparationPlan.version)).where(PreparationPlan.user_id == user_id)) or 0) + 1
    ordered = sorted(ranked, key=lambda row: row[0], reverse=True)
    top_names = ", ".join(skill.canonical_name for _, skill, _ in ordered[:3])
    plan = PreparationPlan(
        user_id=user_id, goal_id=goal.id, version=version,
        summary=f"Seven-day {goal.target_role} plan focused on {top_names}.",
        generation_input={
            "target_role": goal.target_role, "experience_level": goal.experience_level,
            "weekly_hours": goal.weekly_hours, "interests": goal.interests,
        },
    )
    db.add(plan)
    db.flush()
    start = date.today()
    for index, (priority, skill, reasons) in enumerate(ordered[:7]):
        db.add(PreparationTask(
            plan_id=plan.id, skill_id=skill.id,
            title=f"Study and practise {skill.canonical_name}", task_type="revision",
            priority=priority, reasons=reasons, due_date=start + timedelta(days=index),
        ))
    db.commit()
    db.refresh(plan)
    return plan
