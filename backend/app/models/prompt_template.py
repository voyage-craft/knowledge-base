"""User-defined prompt templates for AI operations and workflows."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func, Boolean
from app.core.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), default="custom")  # edit, workflow, chat, generate, custom
    system_prompt = Column(Text, nullable=False)
    input_variables = Column(JSON, nullable=True)  # ["text", "context", "language"]
    output_format = Column(String(20), default="text")  # text, json, tiptap
    is_public = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
