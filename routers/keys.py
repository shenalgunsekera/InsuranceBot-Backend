import secrets
import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from database import get_db
from routers.auth import get_current_admin

router = APIRouter(prefix="/keys", tags=["api-keys"])


def generate_api_key():
    raw = "isk_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, key_hash, raw[:8]


class CreateKeyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    owner_email: Optional[str] = None
    rate_limit: int = Field(default=100, ge=1, le=10000)
    company_name: Optional[str] = None
    bot_name: str = "InsurBot"
    primary_color: str = "#2563eb"
    secondary_color: str = "#1e40af"
    welcome_message: str = "Hello! I'm your insurance assistant. How can I help you today?"
    logo_url: Optional[str] = None


@router.post("")
async def create_key(req: CreateKeyRequest, _=Depends(get_current_admin)):
    raw_key, key_hash, key_prefix = generate_api_key()
    doc_id = str(uuid.uuid4())
    data = {
        'id': doc_id,
        'name': req.name,
        'description': req.description,
        'owner_email': req.owner_email,
        'key_hash': key_hash,
        'key_prefix': key_prefix,
        'is_active': True,
        'rate_limit': req.rate_limit,
        'total_requests': 0,
        'created_at': datetime.utcnow().isoformat(),
        'last_used_at': None,
        'company_name': req.company_name,
        'bot_name': req.bot_name,
        'primary_color': req.primary_color,
        'secondary_color': req.secondary_color,
        'welcome_message': req.welcome_message,
        'logo_url': req.logo_url,
    }
    get_db().collection('api_keys').document(doc_id).set(data)
    return {**data, 'raw_key': raw_key}


@router.get("")
async def list_keys(_=Depends(get_current_admin)):
    db = get_db()
    docs = db.collection('api_keys').order_by('created_at', direction='DESCENDING').stream()
    return [{'id': d.id, **d.to_dict()} for d in docs]


@router.patch("/{key_id}/toggle")
async def toggle_key(key_id: str, _=Depends(get_current_admin)):
    ref = get_db().collection('api_keys').document(key_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(404, "Key not found")
    new_status = not doc.to_dict().get('is_active', True)
    ref.update({'is_active': new_status})
    return {"id": key_id, "is_active": new_status}


@router.delete("/{key_id}")
async def delete_key(key_id: str, _=Depends(get_current_admin)):
    ref = get_db().collection('api_keys').document(key_id)
    if not ref.get().exists:
        raise HTTPException(404, "Key not found")
    ref.delete()
    return {"message": "Key deleted"}
