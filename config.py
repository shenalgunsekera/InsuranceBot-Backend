from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    firebase_credentials: str = ""
    groq_api_key: str = "your-groq-api-key-here"
    groq_model: str = "llama-3.3-70b-versatile"
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    admin_username: str = "admin"
    admin_password: str = "changeme123"
    admin_email: str = "admin@example.com"
    default_rate_limit: int = 100
    rag_top_k: int = 5
    chunk_size: int = 500
    chunk_overlap: int = 50
    upload_dir: str = "./data/uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
