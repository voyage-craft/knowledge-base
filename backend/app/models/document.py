from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Table, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_status", "user_id", "status"),
        Index("ix_documents_user_updated", "user_id", "updated_at"),
        Index("ix_documents_folder_status", "folder_id", "status"),
        Index("ix_documents_user_folder", "user_id", "folder_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, index=True)
    content_json = Column(JSON, nullable=True)  # TipTap JSON
    latex_source = Column(Text, nullable=True)   # Generated LaTeX
    plain_text = Column(Text, nullable=True)      # Extracted plain text for search
    status = Column(String(20), default="draft", index=True)  # draft, published, archived, deleted
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("DocumentVersion", back_populates="document", lazy="noload")
    tags = relationship("Tag", secondary="document_tags", back_populates="documents", lazy="selectin")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    content_json = Column(JSON, nullable=True)
    latex_source = Column(Text, nullable=True)
    version_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="versions")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    position = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#3B82F6")  # hex color
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    documents = relationship("Document", secondary="document_tags", back_populates="tags", lazy="selectin")

# Association table
document_tags = Table(
    "document_tags", Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True, index=True),
)
