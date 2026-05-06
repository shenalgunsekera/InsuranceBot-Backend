from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models.chat_log import ChatLog
from models.api_key import APIKey
from models.document import Document
from routers.auth import get_current_admin
from services.llm_service import llm_service
from services.rag_service import rag_service

router = APIRouter(prefix="/admin", tags=["admin"])


class LogResponse(BaseModel):
    id: str
    api_key_prefix: Optional[str]
    session_id: str
    user_message: str
    assistant_message: Optional[str]
    model_used: Optional[str]
    response_time_ms: Optional[int]
    tokens_estimated: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_keys: int
    active_keys: int
    total_chats: int
    chats_today: int
    total_documents: int
    ready_documents: int
    total_chunks: int
    model_available: bool
    current_model: str


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    total_keys = (await db.execute(select(func.count(APIKey.id)))).scalar()
    active_keys = (await db.execute(select(func.count(APIKey.id)).where(APIKey.is_active == True))).scalar()
    total_chats = (await db.execute(select(func.count(ChatLog.id)))).scalar()

    today = datetime.utcnow().date()
    chats_today = (
        await db.execute(
            select(func.count(ChatLog.id)).where(func.date(ChatLog.created_at) == today)
        )
    ).scalar()

    total_docs = (await db.execute(select(func.count(Document.id)))).scalar()
    ready_docs = (await db.execute(select(func.count(Document.id)).where(Document.status == "ready"))).scalar()

    rag_stats = rag_service.get_stats()
    model_available = await llm_service.is_available()

    return StatsResponse(
        total_keys=total_keys or 0,
        active_keys=active_keys or 0,
        total_chats=total_chats or 0,
        chats_today=chats_today or 0,
        total_documents=total_docs or 0,
        ready_documents=ready_docs or 0,
        total_chunks=rag_stats["total_chunks"],
        model_available=model_available,
        current_model=llm_service.model,
    )


@router.get("/logs", response_model=List[LogResponse])
async def get_logs(
    limit: int = 50,
    offset: int = 0,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    query = select(ChatLog).order_by(ChatLog.created_at.desc()).limit(limit).offset(offset)
    if session_id:
        query = query.where(ChatLog.session_id == session_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/model/status")
async def model_status(_=Depends(get_current_admin)):
    available = await llm_service.is_available()
    models = await llm_service.get_models() if available else []
    return {
        "available": available,
        "current_model": llm_service.model,
        "installed_models": models,
        "provider": "groq",
    }


@router.post("/model/pull")
async def pull_model(
    model_name: str,
    _=Depends(get_current_admin),
):
    from fastapi.responses import StreamingResponse

    async def stream():
        async for line in llm_service.pull_model(model_name):
            yield line + "\n"

    return StreamingResponse(stream(), media_type="text/plain")
