from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CareerGoal, PreparationPlan, PreparationTask, Resume, StudentSkill, User
from app.schemas import (
    CareerGoalIn, CareerGoalOut, PreparationPlanOut, PreparationTaskOut,
    ResumeOut, ResumeProfile, TaskUpdate,
)
from app.security import current_user, require_student
from app.services.career_planning import build_plan, sync_resume_skills
from app.services.resume_parser import process_resume
from app.services.storage import delete_pdf, store_pdf

router = APIRouter(prefix="/career", tags=["student career prep"], dependencies=[Depends(require_student)])


def _resume(db: Session, user_id: int) -> Resume:
    row = db.scalar(select(Resume).where(Resume.user_id == user_id).order_by(Resume.version.desc()))
    if not row:
        raise HTTPException(404, "Resume not found")
    return row


def _goal(db: Session, user_id: int) -> CareerGoal:
    row = db.scalar(select(CareerGoal).where(
        CareerGoal.user_id == user_id, CareerGoal.is_current.is_(True)
    ).order_by(CareerGoal.id.desc()))
    if not row:
        raise HTTPException(404, "Career goal not found")
    return row


def _plan_out(db: Session, plan: PreparationPlan) -> PreparationPlanOut:
    tasks = list(db.scalars(select(PreparationTask).where(
        PreparationTask.plan_id == plan.id
    ).order_by(PreparationTask.priority.desc(), PreparationTask.id)))
    return PreparationPlanOut(
        id=plan.id, goal_id=plan.goal_id, version=plan.version, summary=plan.summary,
        status=plan.status, created_at=plan.created_at,
        tasks=[PreparationTaskOut.model_validate(task) for task in tasks],
    )


@router.post("/resume", response_model=ResumeOut, status_code=202)
async def upload_resume(
    background: BackgroundTasks, file: UploadFile = File(...),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF resumes are supported")
    data = await file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Resume is larger than 5 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a valid PDF")
    latest_version = db.scalar(select(Resume.version).where(Resume.user_id == user.id).order_by(Resume.version.desc())) or 0
    path = store_pdf(user.id, data)
    row = Resume(
        user_id=user.id, filename=Path(file.filename or "resume.pdf").name[:300],
        storage_path=path, version=latest_version + 1,
    )
    try:
        db.add(row); db.commit(); db.refresh(row)
    except Exception:
        db.rollback(); delete_pdf(path); raise
    background.add_task(process_resume, row.id)
    return row


@router.get("/resume", response_model=ResumeOut)
def get_resume(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _resume(db, user.id)


@router.patch("/resume/profile", response_model=ResumeOut)
def confirm_resume_profile(payload: ResumeProfile, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _resume(db, user.id)
    if row.status not in {"review_required", "ready"}:
        raise HTTPException(409, "Resume is not ready for review")
    row.parsed_profile = payload.model_dump()
    row.status = "ready"
    db.execute(delete(StudentSkill).where(StudentSkill.user_id == user.id, StudentSkill.resume_id.is_not(None)))
    sync_resume_skills(db, user.id, row, payload)
    db.commit(); db.refresh(row)
    return row


@router.delete("/resume", status_code=204)
def remove_resume(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Resume).where(Resume.user_id == user.id)))
    if not rows:
        raise HTTPException(404, "Resume not found")
    paths = [row.storage_path for row in rows]
    db.execute(delete(StudentSkill).where(StudentSkill.user_id == user.id, StudentSkill.resume_id.is_not(None)))
    for row in rows:
        db.delete(row)
    db.commit()
    for storage_path in paths:
        delete_pdf(storage_path)


@router.post("/goals", response_model=CareerGoalOut, status_code=201)
def create_goal(payload: CareerGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(CareerGoal).filter(CareerGoal.user_id == user.id, CareerGoal.is_current.is_(True)).update({"is_current": False})
    row = CareerGoal(user_id=user.id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return row


@router.get("/goals/current", response_model=CareerGoalOut)
def current_goal(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _goal(db, user.id)


@router.post("/plans/generate", response_model=PreparationPlanOut, status_code=201)
def generate_plan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    resume = _resume(db, user.id)
    if resume.status != "ready":
        raise HTTPException(409, "Confirm the parsed resume before generating a plan")
    return _plan_out(db, build_plan(db, user.id, _goal(db, user.id)))


@router.get("/plans/current", response_model=PreparationPlanOut)
def current_plan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.scalar(select(PreparationPlan).where(
        PreparationPlan.user_id == user.id, PreparationPlan.status == "active"
    ).order_by(PreparationPlan.version.desc()))
    if not plan:
        raise HTTPException(404, "Preparation plan not found")
    return _plan_out(db, plan)


@router.patch("/tasks/{task_id}", response_model=PreparationTaskOut)
def update_task(task_id: int, payload: TaskUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.scalar(select(PreparationTask).join(PreparationPlan).where(
        PreparationTask.id == task_id, PreparationPlan.user_id == user.id
    ))
    if not task:
        raise HTTPException(404, "Preparation task not found")
    task.completed = payload.completed
    task.completed_at = datetime.now(timezone.utc) if payload.completed else None
    db.commit(); db.refresh(task)
    return task
