from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean
from sqlalchemy.sql import func
import uuid
from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf, docx, txt
    file_size = Column(Integer, nullable=False)  # bytes
    file_path = Column(String(512), nullable=True)
    status = Column(String(20), default="pending")  # pending, processing, ready, error
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    category = Column(String(100), nullable=True)  # e.g., "life_insurance", "sri_lanka_regs"
    description = Column(Text, nullable=True)
    uploaded_by = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
