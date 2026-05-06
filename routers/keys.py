import secrets
import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from database import get_db
from models.api_key import APIKey
from routers.auth import get_current_admin

router = APIRouter(prefix="/keys", tags=["api-keys"])


def generate_api_key() -> tuple[str, str, str]:
    raw = "isk_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:8]
    return raw, key_hash, prefix


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    owner_email: Optional[str] = None
    rate_limit: int = Field(default=100, ge=1, le=10000)
    expires_at: Optional[datetime] = None
    # Branding
    company_name: Optional[str] = None
    bot_name: str = "InsurBot"
    primary_color: str = "#2563eb"
    secondary_color: str = "#1e40af"
    welcome_message: str = "Hello! I'm your insurance assistant. How can I help you today?"
    logo_url: Optional[str] = None


class KeyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    owner_email: Optional[str]
    is_active: bool
    rate_limit: int
    total_requests: int
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    company_name: Optional[str]
    bot_name: str
    primary_color: str
    secondary_color: str
    welcome_message: str
    logo_url: Optional[str]

    class Config:
        from_attributes = True


class CreateKeyResponse(KeyResponse):
    raw_key: str


@router.post("", response_model=CreateKeyResponse)
async def create_key(
    req: CreateKeyRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        owner_email=req.owner_email,
        key_hash=key_hash,
        key_prefix=key_prefix,
        rate_limit=req.rate_limit,
        expires_at=req.expires_at,
        company_name=req.company_name,
        bot_name=req.bot_name,
        primary_color=req.primary_color,
        secondary_color=req.secondary_color,
        welcome_message=req.welcome_message,
        logo_url=req.logo_url,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return CreateKeyResponse(
        **{c.name: getattr(api_key, c.name) for c in APIKey.__table__.columns},
        raw_key=raw_key,
    )


@router.get("", response_model=List[KeyResponse])
async def list_keys(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))
    return result.scalars().all()


@router.get("/{key_id}", response_model=KeyResponse)
async def get_key(key_id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    return key


@router.patch("/{key_id}/toggle")
async def toggle_key(key_id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    await db.execute(update(APIKey).where(APIKey.id == key_id).values(is_active=not key.is_active))
    await db.commit()
    return {"id": key_id, "is_active": not key.is_active}


@router.delete("/{key_id}")
async def delete_key(key_id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    await db.delete(key)
    await db.commit()
    return {"message": "Key deleted"}
