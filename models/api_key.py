from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text
from sqlalchemy.sql import func
import uuid
from database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    key_prefix = Column(String(8), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    owner_email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)
    total_requests = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # ── Branding ──────────────────────────────────────────────────────────────
    company_name = Column(String(100), nullable=True)
    bot_name = Column(String(100), default="InsurBot")
    primary_color = Column(String(7), default="#2563eb")   # hex
    secondary_color = Column(String(7), default="#1e40af")
    welcome_message = Column(Text, default="Hello! I'm your insurance assistant. How can I help you today?")
    logo_url = Column(String(512), nullable=True)
