from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Membership, Tenant, User
from app.schemas import AuthIn, PasswordUpdate, ProfileUpdate, TokenOut
from app.security import current_user, hash_password, make_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: AuthIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Email is already registered")
    tenant = Tenant(name=f"{payload.email.split('@')[0]}'s institution", slug=f"institution-{uuid4().hex[:12]}")
    db.add(tenant)
    db.flush()
    user = User(email=payload.email.lower(), first_name=payload.first_name.strip().title() if payload.first_name else None, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    role = "student" if payload.account_type == "student" else "admin"
    db.add(Membership(tenant_id=tenant.id, user_id=user.id, role=role))
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=make_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(payload: AuthIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.id))
    is_teacher = bool(membership and membership.role in {"teacher", "hod", "admin"})
    if payload.account_type == "teacher" and not is_teacher:
        raise HTTPException(403, "This is a student account. Use Student login.")
    if payload.account_type == "student" and is_teacher:
        raise HTTPException(403, "This is a teacher account. Use Teacher login.")
    return TokenOut(access_token=make_token(user.id))


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.id))
    name = user.first_name or user.email.split("@", 1)[0].replace(".", " ").replace("_", " ").strip().title()
    tenant = db.get(Tenant, membership.tenant_id) if membership else None
    return {
        "id": user.id, "email": user.email, "name": name,
        "role": membership.role if membership else None,
        "institution": tenant.name if tenant else None,
    }


@router.patch("/me")
def update_me(payload: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.first_name = payload.first_name.strip().title()
    db.commit()
    return {"first_name": user.first_name}


@router.post("/password")
def update_password(payload: PasswordUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(400, "New password must be different")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"status": "updated"}
