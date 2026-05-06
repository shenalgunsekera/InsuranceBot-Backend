import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from auth_utils import hash_password

from config import settings
from database import init_db, AsyncSessionLocal
from models import AdminUser
from services.rag_service import rag_service
from routers import auth, chat, keys, documents, admin
from routers.widget_config import router as widget_router


async def _seed_admin():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, update
        result = await db.execute(select(AdminUser).where(AdminUser.username == settings.admin_username))
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(AdminUser(
                username=settings.admin_username,
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
            ))
            await db.commit()
            logger.info(f"Created admin: {settings.admin_username}")
        else:
            # Always sync password from env var on startup
            await db.execute(
                update(AdminUser)
                .where(AdminUser.username == settings.admin_username)
                .values(hashed_password=hash_password(settings.admin_password))
            )
            await db.commit()
            logger.info(f"Synced admin password from env")


async def _load_builtin_knowledge():
    if rag_service.get_stats()["total_chunks"] > 0:
        return  # already loaded
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
            await rag_service.add_documents(chunks, f"builtin_{fname}", fname, fname.replace(".txt", ""))
            logger.info(f"Loaded knowledge: {fname} ({len(chunks)} chunks)")
        except Exception as e:
            logger.warning(f"Could not load {fname}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting IS ChatBot API...")
    os.makedirs("./data/uploads", exist_ok=True)
    os.makedirs("./data/chroma_db", exist_ok=True)
    await init_db()
    await _seed_admin()
    try:
        await _load_builtin_knowledge()
    except Exception as e:
        logger.warning(f"Knowledge load skipped (Ollama not ready yet?): {e}")
    logger.info("API ready at http://localhost:8000")
    yield


app = FastAPI(title="IS ChatBot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # widget must load from any domain
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
    from services.llm_service import llm_service
    ok = await llm_service.is_available()
    return {"status": "ok", "llm": "online" if ok else "offline", "chunks": rag_service.get_stats()["total_chunks"]}

@app.get("/")
async def root():
    return {"name": "IS ChatBot API", "docs": "/docs"}
