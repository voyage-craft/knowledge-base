from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.core.database import Base

class ExportJob(Base):
    __tablename__ = "export_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    format = Column(String(20), nullable=False)  # pdf, docx, html, epub, markdown
    template_name = Column(String(100), default="default")
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    output_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
