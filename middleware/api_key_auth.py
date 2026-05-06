import hashlib
from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select, update
from sqlalchemy.sql import func
from database import AsyncSessionLocal
from models.api_key import APIKey
from services.session_service import session_service
from loguru import logger

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(request: Request) -> APIKey:
    """Extract and validate API key from request headers."""
    raw_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Pass it as X-API-Key header.",
        )

    key_hash = hash_key(raw_key)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or inactive API key.",
            )

        # Check expiry
        if api_key.expires_at:
            from datetime import datetime, timezone
            if datetime.now(timezone.utc) > api_key.expires_at:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key has expired.",
                )

        # Rate limiting
        allowed, remaining = await session_service.rate_limit_check(
            api_key.id, api_key.rate_limit
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {api_key.rate_limit} requests/hour.",
                headers={"X-RateLimit-Remaining": "0"},
            )

        # Update last_used_at and request count
        await db.execute(
            update(APIKey)
            .where(APIKey.id == api_key.id)
            .values(last_used_at=func.now(), total_requests=APIKey.total_requests + 1)
        )
        await db.commit()

    return api_key
