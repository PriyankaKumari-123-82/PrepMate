from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentRun, AgentStep, Approval, Artifact, Course, LearningOutcome, Membership, Review, Subject, Unit, User
from app.schemas import (
    ArtifactOut, ArtifactPatch, CourseCreate, CourseOut, DecisionIn, GenerateArtifactIn,
    OutcomeCreate, SubjectCreate, SubjectOut, UnitCreate,
)
from app.security import current_membership, current_user, require_teacher
from app.services.workflows import generate_artifact

router = APIRouter(tags=["teacher copilot"], dependencies=[Depends(require_teacher)])


def _tenant_row(db: Session, model, row_id: int, membership: Membership):
    row = db.get(model, row_id)
    if not row or getattr(row, "tenant_id", None) != membership.tenant_id:
        raise HTTPException(404, "Resource not found")
    return row


def _artifact(db: Session, artifact_id: int, membership: Membership) -> Artifact:
    return _tenant_row(db, Artifact, artifact_id, membership)


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(payload: SubjectCreate, membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    row = Subject(tenant_id=membership.tenant_id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return row


@router.get("/subjects", response_model=list[SubjectOut])
def subjects(membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    return list(db.scalars(select(Subject).where(Subject.tenant_id == membership.tenant_id).order_by(Subject.name)))


@router.post("/courses", response_model=CourseOut, status_code=201)
def create_course(payload: CourseCreate, user: User = Depends(current_user), membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    _tenant_row(db, Subject, payload.subject_id, membership)
    row = Course(tenant_id=membership.tenant_id, owner_id=user.id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return row


@router.get("/courses", response_model=list[CourseOut])
def courses(membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    return list(db.scalars(select(Course).where(Course.tenant_id == membership.tenant_id).order_by(Course.created_at.desc())))


@router.post("/courses/{course_id}/units", status_code=201)
def create_unit(course_id: int, payload: UnitCreate, membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    _tenant_row(db, Course, course_id, membership)
    row = Unit(course_id=course_id, **payload.model_dump()); db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "course_id": row.course_id, "title": row.title, "order_idx": row.order_idx}


@router.post("/units/{unit_id}/outcomes", status_code=201)
def create_outcome(unit_id: int, payload: OutcomeCreate, membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    unit = db.get(Unit, unit_id)
    if not unit: raise HTTPException(404, "Unit not found")
    _tenant_row(db, Course, unit.course_id, membership)
    row = LearningOutcome(unit_id=unit_id, **payload.model_dump()); db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, **payload.model_dump()}


@router.post("/artifacts/generate", response_model=ArtifactOut, status_code=201)
async def generate(payload: GenerateArtifactIn, user: User = Depends(current_user), membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if payload.course_id is not None: _tenant_row(db, Course, payload.course_id, membership)
    from app.api.documents import owned_document
    for document_id in payload.document_ids:
        document = owned_document(db, document_id, user.id)
        if document.status != "ready": raise HTTPException(409, f"Document {document_id} is not ready")
    try:
        _, artifact = await generate_artifact(db, membership.tenant_id, user, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return artifact


@router.get("/artifacts", response_model=list[ArtifactOut])
def artifacts(membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    return list(db.scalars(select(Artifact).where(Artifact.tenant_id == membership.tenant_id).order_by(Artifact.created_at.desc())))


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def artifact(artifact_id: int, membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    return _artifact(db, artifact_id, membership)


@router.patch("/artifacts/{artifact_id}", response_model=ArtifactOut)
def edit_artifact(artifact_id: int, payload: ArtifactPatch, user: User = Depends(current_user), membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    row = _artifact(db, artifact_id, membership)
    if row.owner_id != user.id and membership.role not in {"hod", "admin"}: raise HTTPException(403, "Insufficient role")
    for key, value in payload.model_dump(exclude_none=True).items(): setattr(row, key, value)
    row.version += 1
    if row.status != "draft": row.status = "draft"
    db.commit(); db.refresh(row); return row


@router.post("/artifacts/{artifact_id}/review")
def review_artifact(artifact_id: int, user: User = Depends(current_user), membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    row = _artifact(db, artifact_id, membership)
    issues = [] if row.sources else ["Artifact has no citations"]
    report = {"grounded": bool(row.sources), "source_count": len(row.sources), "issues": issues}
    db.add(Review(artifact_id=row.id, reviewer_id=user.id, verdict="pass" if not issues else "fail", report=report))
    db.commit(); return report


@router.post("/artifacts/{artifact_id}/submit")
def submit(artifact_id: int, user: User = Depends(current_user), membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    row = _artifact(db, artifact_id, membership)
    if row.owner_id != user.id: raise HTTPException(403, "Only the owner can submit this artifact")
    row.status = "in_review"; db.add(Approval(artifact_id=row.id, requested_by=user.id)); db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/artifacts/{artifact_id}/approve")
def approve(artifact_id: int, payload: DecisionIn, user: User = Depends(current_user), membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if membership.role not in {"hod", "admin"}: raise HTTPException(403, "HOD or admin role required")
    row = _artifact(db, artifact_id, membership)
    approval = db.scalar(select(Approval).where(Approval.artifact_id == row.id, Approval.decision == "pending").order_by(Approval.id.desc()))
    if not approval: raise HTTPException(409, "Artifact is not awaiting approval")
    approval.decision, approval.decided_by, approval.comment = payload.decision, user.id, payload.comment
    row.status = "approved" if payload.decision == "approved" else "draft"
    db.commit(); return {"id": row.id, "status": row.status, "decision": approval.decision}


@router.get("/runs/{run_id}")
def run_detail(run_id: int, membership: Membership = Depends(current_membership), db: Session = Depends(get_db)):
    run = _tenant_row(db, AgentRun, run_id, membership)
    steps = list(db.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.id)))
    return {
        "id": run.id, "workflow": run.workflow, "status": run.status, "input": run.input,
        "output": run.output, "error": run.error,
        "steps": [{"id": step.id, "agent": step.agent, "status": step.status, "output": step.output} for step in steps],
    }
