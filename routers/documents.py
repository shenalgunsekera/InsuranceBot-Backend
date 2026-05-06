import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from models.document import Document
from routers.auth import get_current_admin
from services.rag_service import rag_service
from utils.document_processor import extract_text_from_file, chunk_text
from config import settings
from loguru import logger

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_TYPES = {".pdf", ".docx", ".txt", ".md"}


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    category: Optional[str]
    description: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]
    class Config:
        from_attributes = True


async def _process_document(doc_id: str, file_path: str, filename: str, category: str):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(update(Document).where(Document.id == doc_id).values(status="processing"))
            await db.commit()

            text = extract_text_from_file(file_path)
            if not text.strip():
                raise ValueError("Document contains no extractable text")

            chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
            count = await rag_service.add_documents(chunks, doc_id, filename, category)

            await db.execute(update(Document).where(Document.id == doc_id).values(
                status="ready", chunk_count=count, processed_at=func.now()
            ))
            await db.commit()
            logger.info(f"Document {doc_id} ready: {count} chunks")
        except Exception as e:
            logger.error(f"Document processing failed {doc_id}: {e}")
            await db.execute(update(Document).where(Document.id == doc_id).values(
                status="error", error_message=str(e)[:500]
            ))
            await db.commit()


@router.post("", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(default="general"),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(ALLOWED_TYPES)}")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}{ext}"
    save_path = os.path.join(settings.upload_dir, safe_name)
    os.makedirs(settings.upload_dir, exist_ok=True)

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    doc = Document(
        id=doc_id, filename=safe_name, original_filename=file.filename,
        file_type=ext.lstrip("."), file_size=len(content), file_path=save_path,
        status="pending", category=category, description=description, uploaded_by=admin.username,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    background_tasks.add_task(_process_document, doc_id, save_path, file.filename, category)
    return doc


@router.get("", response_model=List[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    rag_service.delete_document(doc_id)
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted"}
