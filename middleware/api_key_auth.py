import hashlib
from fastapi import Request, HTTPException, status
from database import get_db
from services.session_service import session_service


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(request: Request) -> dict:
    raw_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not raw_key:
        raise HTTPException(status_code=401, detail="API key required. Pass as X-API-Key header.")

    key_hash = hash_key(raw_key)
    db = get_db()
    docs = list(db.collection('api_keys').where('key_hash', '==', key_hash).where('is_active', '==', True).limit(1).stream())

    if not docs:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key.")

    api_key = docs[0].to_dict()
    api_key['id'] = docs[0].id

    allowed, remaining = await session_service.rate_limit_check(api_key['id'], api_key.get('rate_limit', 100))
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    # Update last_used
    docs[0].reference.update({'last_used_at': __import__('datetime').datetime.utcnow().isoformat(), 'total_requests': api_key.get('total_requests', 0) + 1})
    return api_key
