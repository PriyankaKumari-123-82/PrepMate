from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Membership, ProviderCredential, Tenant, TenantModelSettings, User
from app.schemas import ModelSettingsUpdate, ProviderKeyCreate
from app.security import current_membership, current_user, require_teacher
from app.services.secrets import encrypt_secret

router = APIRouter(prefix="/settings", tags=["organization settings"], dependencies=[Depends(require_teacher)])

PROVIDERS = [
    {"id": "openai", "name": "OpenAI"},
    {"id": "anthropic", "name": "Anthropic"},
    {"id": "gemini", "name": "Google Gemini"},
    {"id": "mistral", "name": "Mistral"},
    {"id": "groq", "name": "Groq"},
    {"id": "cohere", "name": "Cohere"},
    {"id": "zai", "name": "Z.ai"},
]


def _can_manage(membership: Membership) -> None:
    if membership.role not in {"hod", "admin"}:
        raise HTTPException(403, "Institution admin or HOD role required")


def _models(db: Session, tenant_id: int) -> TenantModelSettings:
    row = db.get(TenantModelSettings, tenant_id)
    if not row:
        config = get_settings()
        row = TenantModelSettings(
            tenant_id=tenant_id,
            generation_provider="openai",
            generation_model=config.llm_model,
            embedding_provider="openai",
            embedding_model=config.embed_model,
        )
        db.add(row)
        db.flush()
    return row


def _credential_out(row: ProviderCredential) -> dict:
    return {
        "id": row.id,
        "provider": row.provider,
        "label": row.label,
        "masked_key": f"••••••••{row.key_suffix}",
        "is_default": row.is_default,
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
    }


@router.get("")
def get_organization_settings(
    membership: Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    tenant = db.get(Tenant, membership.tenant_id)
    models = _models(db, membership.tenant_id)
    credentials = list(db.scalars(select(ProviderCredential).where(
        ProviderCredential.tenant_id == membership.tenant_id
    ).order_by(ProviderCredential.created_at.desc())))
    db.commit()
    return {
        "organization": {"id": tenant.id, "name": tenant.name},
        "can_manage": membership.role in {"hod", "admin"},
        "provider_catalog": PROVIDERS,
        "models": {
            "generation_provider": models.generation_provider,
            "generation_model": models.generation_model,
            "embedding_provider": models.embedding_provider,
            "embedding_model": models.embedding_model,
        },
        "api_keys": [_credential_out(row) for row in credentials],
    }


@router.put("/models")
def update_model_settings(
    payload: ModelSettingsUpdate,
    membership: Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _can_manage(membership)
    row = _models(db, membership.tenant_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    return {"status": "updated", "models": payload.model_dump()}


@router.post("/api-keys", status_code=201)
def add_provider_key(
    payload: ProviderKeyCreate,
    user: User = Depends(current_user),
    membership: Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _can_manage(membership)
    key = payload.api_key.strip()
    make_default = payload.make_default or not db.scalar(select(ProviderCredential.id).where(
        ProviderCredential.tenant_id == membership.tenant_id
    ).limit(1))
    if make_default:
        db.execute(update(ProviderCredential).where(
            ProviderCredential.tenant_id == membership.tenant_id
        ).values(is_default=False))
    provider_name = next(item["name"] for item in PROVIDERS if item["id"] == payload.provider)
    row = ProviderCredential(
        tenant_id=membership.tenant_id,
        provider=payload.provider,
        label=(payload.label or provider_name).strip(),
        encrypted_api_key=encrypt_secret(key),
        key_suffix=key[-4:],
        is_default=make_default,
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _credential_out(row)


def _owned_credential(db: Session, credential_id: int, tenant_id: int) -> ProviderCredential:
    row = db.scalar(select(ProviderCredential).where(
        ProviderCredential.id == credential_id,
        ProviderCredential.tenant_id == tenant_id,
    ))
    if not row:
        raise HTTPException(404, "Provider key not found")
    return row


@router.post("/api-keys/{credential_id}/default")
def make_default_key(
    credential_id: int,
    membership: Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _can_manage(membership)
    row = _owned_credential(db, credential_id, membership.tenant_id)
    db.execute(update(ProviderCredential).where(
        ProviderCredential.tenant_id == membership.tenant_id
    ).values(is_default=False))
    row.is_default = True
    db.commit()
    return _credential_out(row)


@router.delete("/api-keys/{credential_id}", status_code=204)
def delete_provider_key(
    credential_id: int,
    membership: Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    _can_manage(membership)
    row = _owned_credential(db, credential_id, membership.tenant_id)
    was_default = row.is_default
    db.delete(row)
    db.flush()
    if was_default:
        replacement = db.scalar(select(ProviderCredential).where(
            ProviderCredential.tenant_id == membership.tenant_id
        ).order_by(ProviderCredential.created_at).limit(1))
        if replacement:
            replacement.is_default = True
    db.commit()
    return Response(status_code=204)
