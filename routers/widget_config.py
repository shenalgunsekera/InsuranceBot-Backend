import hashlib
from fastapi import APIRouter, HTTPException, Query
from database import get_db

router = APIRouter(prefix="/widget", tags=["widget"])


@router.get("/config")
async def get_widget_config(key: str = Query(...)):
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    db = get_db()
    docs = list(db.collection('api_keys').where('key_hash', '==', key_hash).where('is_active', '==', True).limit(1).stream())
    if not docs:
        raise HTTPException(403, "Invalid API key")
    d = docs[0].to_dict()
    return {
        "company_name": d.get('company_name') or d.get('name', 'InsurBot'),
        "bot_name": d.get('bot_name', 'InsurBot'),
        "primary_color": d.get('primary_color', '#2563eb'),
        "secondary_color": d.get('secondary_color', '#1e40af'),
        "welcome_message": d.get('welcome_message', 'Hello! How can I help you?'),
        "logo_url": d.get('logo_url'),
    }
