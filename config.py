from pydantic_settings import BaseSettings
from typing import List
import json, os


class Settings(BaseSettings):
    # Database — SQLite locally, PostgreSQL on Railway
    database_url: str = "sqlite+aiosqlite:///./data/chatbot.db"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # Railway sets DATABASE_URL as postgres:// — convert to asyncpg
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Groq LLM
    groq_api_key: str = "your-groq-api-key-here"
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama (fallback / embedding)
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 120

    # Security
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Admin
    admin_username: str = "admin"
    admin_password: str = "changeme123"
    admin_email: str = "admin@example.com"

    # API
    default_rate_limit: int = 100
    cors_origins: List[str] = ["*"]

    # RAG
    chroma_path: str = "./data/chroma_db"
    upload_dir: str = "./data/uploads"
    chunk_size: int = 500
    chunk_overlap: int = 50
    rag_top_k: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
