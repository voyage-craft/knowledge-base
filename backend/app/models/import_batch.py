from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/processing/review/completed/failed
    total_files = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ImportFile(Base):
    __tablename__ = "import_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # md/docx/pdf/txt/tex
    raw_text = Column(Text, nullable=True)
    ai_analysis = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/analyzing/ready/rejected/imported/error
    error_message = Column(Text, nullable=True)
    imported_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
