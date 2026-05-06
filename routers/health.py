from fastapi import APIRouter
from services.llm_service import llm_service
from services.rag_service import rag_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    llm_ok = await llm_service.is_available()
    rag_stats = rag_service.get_stats()
    return {
        "status": "ok",
        "llm": "online" if llm_ok else "offline",
        "rag_chunks": rag_stats["total_chunks"],
        "model": llm_service.model,
    }
