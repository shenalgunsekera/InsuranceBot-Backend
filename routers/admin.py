from fastapi import APIRouter, Depends
from database import get_db
from routers.auth import get_current_admin
from services.llm_service import llm_service
from services.rag_service import rag_service
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(_=Depends(get_current_admin)):
    db = get_db()
    keys = list(db.collection('api_keys').stream())
    active_keys = sum(1 for k in keys if k.to_dict().get('is_active'))
    logs = list(db.collection('chat_logs').limit(10000).stream())
    today = datetime.utcnow().date().isoformat()
    chats_today = sum(1 for l in logs if l.to_dict().get('created_at', '')[:10] == today)
    docs = list(db.collection('documents').stream())
    ready_docs = sum(1 for d in docs if d.to_dict().get('status') == 'ready')
    rag_stats = rag_service.get_stats()
    model_ok = await llm_service.is_available()
    return {
        "total_keys": len(keys),
        "active_keys": active_keys,
        "total_chats": len(logs),
        "chats_today": chats_today,
        "total_documents": len(docs),
        "ready_documents": ready_docs,
        "total_chunks": rag_stats["total_chunks"],
        "model_available": model_ok,
        "current_model": llm_service.model,
    }


@router.get("/logs")
async def get_logs(limit: int = 50, offset: int = 0, _=Depends(get_current_admin)):
    db = get_db()
    docs = list(db.collection('chat_logs').order_by('created_at', direction='DESCENDING').limit(limit).stream())
    return [{'id': d.id, **d.to_dict()} for d in docs]


@router.get("/model/status")
async def model_status(_=Depends(get_current_admin)):
    available = await llm_service.is_available()
    models = await llm_service.get_models() if available else []
    return {"available": available, "current_model": llm_service.model, "installed_models": models, "provider": "groq"}
