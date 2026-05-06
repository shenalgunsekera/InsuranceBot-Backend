import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import settings
from database import init_firebase, get_db
from auth_utils import hash_password
from services.rag_service import rag_service
from routers import auth, chat, keys, documents, admin
from routers.widget_config import router as widget_router


def _seed_admin():
    db = get_db()
    docs = list(db.collection('admin_users').where('username', '==', settings.admin_username).limit(1).stream())
    hashed = hash_password(settings.admin_password)
    if not docs:
        db.collection('admin_users').add({
            'username': settings.admin_username,
            'email': settings.admin_email,
            'hashed_password': hashed,
        })
        logger.info(f"Created admin: {settings.admin_username}")
    else:
        docs[0].reference.update({'hashed_password': hashed})
        logger.info("Admin password synced")


def _load_builtin_knowledge():
    if rag_service.get_stats()["total_chunks"] > 0:
        return
    knowledge_dir = os.path.join(os.path.dirname(__file__), "data", "insurance_knowledge")
    if not os.path.exists(knowledge_dir):
        return
    from utils.document_processor import extract_text_from_file, chunk_text
    for fname in os.listdir(knowledge_dir):
        if not fname.endswith(".txt"):
            continue
        try:
            text = extract_text_from_file(os.path.join(knowledge_dir, fname))
            chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
            rag_service.add_documents(chunks, f"builtin_{fname}", fname, fname.replace(".txt", ""))
            logger.info(f"Loaded: {fname} ({len(chunks)} chunks)")
        except Exception as e:
            logger.warning(f"Could not load {fname}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting IS ChatBot...")
    try:
        init_firebase()
        _seed_admin()
        _load_builtin_knowledge()
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    logger.info("Ready.")
    yield


app = FastAPI(title="IS ChatBot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(keys.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(widget_router)


@app.get("/health")
async def health():
    return {"status": "ok", "db": "firebase", "chunks": rag_service.get_stats()["total_chunks"]}


@app.get("/")
async def root():
    return {"name": "IS ChatBot API", "docs": "/docs"}
