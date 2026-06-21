"""Collaboration models for document sharing, comments, and annotations.

This module provides models for multi-user collaboration features:
- Document sharing with permission control
- Document locking for conflict prevention
- Comments and annotations with threading support
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.core.database import Base


class DocumentShare(Base):
    """Document sharing permissions between users.

    Permission levels:
    - read: Can view the document
    - write: Can view and edit the document
    - admin: Can view, edit, and manage sharing
    """

    __tablename__ = "document_shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shared_with_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(20), default="read", nullable=False)  # read, write, admin

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "shared_with_id", name="uq_document_share"),
    )

    def __repr__(self):
        return f"<DocumentShare(doc={self.document_id}, user={self.shared_with_id}, perm={self.permission})>"


class DocumentLock(Base):
    """Document locking to prevent concurrent edit conflicts.

    Lock types:
    - edit: User is actively editing
    - review: Document is in review state
    """

    __tablename__ = "document_locks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False)
    locked_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lock_type = Column(String(20), default="edit", nullable=False)  # edit, review

    locked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Auto-release after expiry

    def __repr__(self):
        return f"<DocumentLock(doc={self.document_id}, user={self.locked_by_id}, type={self.lock_type})>"


class Comment(Base):
    """Comments and annotations on documents.

    Supports:
    - Top-level comments on documents
    - Threaded replies (via parent_id)
    - Inline annotations (via anchor positions)
    - Resolution tracking
    """

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)

    content = Column(Text, nullable=False)

    # Inline annotation support
    anchor_start = Column(Integer, nullable=True)  # Character offset start
    anchor_end = Column(Integer, nullable=True)  # Character offset end
    annotation_text = Column(String(500), nullable=True)  # Highlighted text snippet

    # Status tracking
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_comment_doc_resolved", "document_id", "is_resolved"),
    )

    def __repr__(self):
        return f"<Comment(id={self.id}, doc={self.document_id}, user={self.user_id})>"


class CommentReaction(Base):
    """Emoji reactions on comments.

    Supported emojis:
    - thumbs_up: Agreement
    - heart: Appreciation
    - check: Acknowledgment
    - question: Need clarification
    """

    __tablename__ = "comment_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(10), nullable=False)  # thumbs_up, heart, check, question

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", "emoji", name="uq_comment_reaction"),
    )

    def __repr__(self):
        return f"<CommentReaction(comment={self.comment_id}, user={self.user_id}, emoji={self.emoji})>"
