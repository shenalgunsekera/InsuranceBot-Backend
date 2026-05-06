from sqlalchemy import Column, String, Integer, DateTime, Text, Float
from sqlalchemy.sql import func
import uuid
from database import Base


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String, nullable=True, index=True)
    api_key_prefix = Column(String(8), nullable=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    assistant_message = Column(Text, nullable=True)
    sources_used = Column(Text, nullable=True)  # JSON list of source documents
    model_used = Column(String(50), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    tokens_estimated = Column(Integer, nullable=True)
    language_detected = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
