import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from database import get_db
from routers.auth import get_current_admin
from services.rag_service import rag_service
from utils.document_processor import extract_text_from_file, chunk_text
from config import settings
from loguru import logger
from datetime import datetime

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED = {".pdf", ".docx", ".txt", ".md"}


async def _process(doc_id: str, file_path: str, filename: str, category: str):
    db = get_db()
    try:
        db.collection('documents').document(doc_id).update({'status': 'processing'})
        text = extract_text_from_file(file_path)
        if not text.strip():
            raise ValueError("No extractable text")
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        count = rag_service.add_documents(chunks, doc_id, filename, category)
        db.collection('documents').document(doc_id).update({'status': 'ready', 'chunk_count': count, 'processed_at': datetime.utcnow().isoformat()})
        logger.info(f"Processed {filename}: {count} chunks")
    except Exception as e:
        logger.error(f"Processing failed {doc_id}: {e}")
        db.collection('documents').document(doc_id).update({'status': 'error', 'error_message': str(e)[:500]})


@router.post("")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                           category: str = Form(default="general"), description: str = Form(default=""),
                           admin=Depends(get_current_admin)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported type. Allowed: {', '.join(ALLOWED)}")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}{ext}"
    os.makedirs(settings.upload_dir, exist_ok=True)
    save_path = os.path.join(settings.upload_dir, safe_name)
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    data = {
        'id': doc_id, 'filename': safe_name, 'original_filename': file.filename,
        'file_type': ext.lstrip('.'), 'file_size': len(content), 'file_path': save_path,
        'status': 'pending', 'chunk_count': 0, 'category': category,
        'description': description, 'uploaded_by': admin['username'],
        'created_at': datetime.utcnow().isoformat(), 'processed_at': None, 'error_message': None,
    }
    get_db().collection('documents').document(doc_id).set(data)
    background_tasks.add_task(_process, doc_id, save_path, file.filename, category)
    return data


@router.get("")
async def list_documents(_=Depends(get_current_admin)):
    db = get_db()
    docs = db.collection('documents').order_by('created_at', direction='DESCENDING').stream()
    return [{'id': d.id, **d.to_dict()} for d in docs]


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, _=Depends(get_current_admin)):
    db = get_db()
    ref = db.collection('documents').document(doc_id)
    if not ref.get().exists:
        raise HTTPException(404, "Not found")
    rag_service.delete_document(doc_id)
    ref.delete()
    return {"message": "Deleted"}
