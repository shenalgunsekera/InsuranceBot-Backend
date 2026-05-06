import time
import json
import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncIterator
from loguru import logger
from database import get_db
from middleware.api_key_auth import verify_api_key
from services.llm_service import llm_service
from services.rag_service import rag_service
from services.session_service import session_service
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    stream: bool = True
    model: Optional[str] = None


@router.post("")
async def chat(req: ChatRequest, request: Request, api_key: dict = Depends(verify_api_key)):
    session_id = req.session_id or str(uuid.uuid4())
    start_time = time.time()
    history = await session_service.get_history(session_id)
    context, sources = rag_service.build_context(req.message)

    if req.stream:
        return StreamingResponse(
            _stream(req, session_id, history, context, sources, api_key, start_time),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response_text = await llm_service.generate(req.message, context, history, req.model)
    elapsed_ms = int((time.time() - start_time) * 1000)
    await _save_log(api_key, session_id, req.message, response_text, sources, elapsed_ms)
    await session_service.add_turn(session_id, req.message, response_text)
    return {"response": response_text, "session_id": session_id, "sources": sources, "model": req.model or llm_service.model}


async def _stream(req, session_id, history, context, sources, api_key, start_time) -> AsyncIterator[str]:
    full_response = ""
    yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
    if sources:
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    try:
        async for token in llm_service.generate_stream(req.message, context, history, req.model):
            full_response += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        elapsed_ms = int((time.time() - start_time) * 1000)
        yield f"data: {json.dumps({'type': 'done', 'elapsed_ms': elapsed_ms})}\n\n"
        await _save_log(api_key, session_id, req.message, full_response, sources, elapsed_ms)
        await session_service.add_turn(session_id, req.message, full_response)
    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


async def _save_log(api_key, session_id, user_message, assistant_message, sources, elapsed_ms):
    try:
        db = get_db()
        log_id = str(uuid.uuid4())
        db.collection('chat_logs').document(log_id).set({
            'api_key_id': api_key.get('id'),
            'api_key_prefix': api_key.get('key_prefix'),
            'session_id': session_id,
            'user_message': user_message,
            'assistant_message': assistant_message,
            'sources_used': sources,
            'model_used': llm_service.model,
            'response_time_ms': elapsed_ms,
            'created_at': datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.warning(f"Log save failed: {e}")


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, api_key: dict = Depends(verify_api_key)):
    await session_service.clear_session(session_id)
    return {"message": "Session cleared"}
