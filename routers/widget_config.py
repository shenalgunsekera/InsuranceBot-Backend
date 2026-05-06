import hashlib
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from database import AsyncSessionLocal
from models.api_key import APIKey

router = APIRouter(prefix="/widget", tags=["widget"])


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


@router.get("/config")
async def get_widget_config(key: str = Query(..., description="API key")):
    """Public endpoint — widget fetches branding config using its API key."""
    key_hash = hash_key(key)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(403, "Invalid API key")

    return {
        "company_name": api_key.company_name or api_key.name,
        "bot_name": api_key.bot_name or "InsurBot",
        "primary_color": api_key.primary_color or "#2563eb",
        "secondary_color": api_key.secondary_color or "#1e40af",
        "welcome_message": api_key.welcome_message or "Hello! How can I help you?",
        "logo_url": api_key.logo_url,
    }
