"""User activity tracking model for recommendation engine and analytics.

This module provides models for tracking user interactions with documents,
which feeds into the recommendation system and analytics dashboard.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class UserActivity(Base):
    """Tracks user interactions with documents.

    Activity types:
    - view: User viewed a document
    - edit: User edited a document
    - search: User performed a search
    - bookmark: User bookmarked a document
    - share: User shared a document
    - export: User exported a document
    - import: User imported a document
    """

    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    activity_type = Column(String(20), nullable=False, index=True)

    # Optional metadata
    duration_seconds = Column(Integer, nullable=True)  # For view events
    search_query = Column(String(500), nullable=True)  # For search events
    metadata_json = Column(Text, nullable=True)  # Additional JSON metadata

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_user_activity_user_doc", "user_id", "document_id"),
        Index("ix_user_activity_type_time", "activity_type", "created_at"),
        Index("ix_user_activity_user_time", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, type={self.activity_type})>"


class DocumentRelation(Base):
    """Stores relationships between documents for recommendation engine.

    Relation types:
    - similar_content: Documents with similar embeddings
    - shared_entities: Documents sharing knowledge graph entities
    - co_viewed: Documents frequently viewed by same users
    - co_edited: Documents frequently edited by same users
    """

    __tablename__ = "document_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(30), nullable=False, index=True)
    score = Column(Integer, default=0)  # Similarity score (0-1000 for precision)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_doc_relation_source_type", "source_doc_id", "relation_type"),
        Index("ix_doc_relation_target_type", "target_doc_id", "relation_type"),
    )

    def __repr__(self):
        return f"<DocumentRelation(source={self.source_doc_id}, target={self.target_doc_id}, type={self.relation_type})>"


class UserRecommendation(Base):
    """Stores personalized recommendations for users.

    Algorithm types:
    - content_based: Based on document content similarity
    - collaborative: Based on similar users' behavior
    - graph_based: Based on knowledge graph connections
    - hybrid: Combination of multiple algorithms
    """

    __tablename__ = "user_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(200), nullable=True)  # Human-readable reason
    score = Column(Integer, default=0)  # Recommendation score (0-1000)
    algorithm = Column(String(30), nullable=False, index=True)
    is_dismissed = Column(Integer, default=0)  # 0=active, 1=dismissed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_user_rec_user_algo", "user_id", "algorithm"),
        Index("ix_user_rec_user_score", "user_id", "score"),
    )

    def __repr__(self):
        return f"<UserRecommendation(user_id={self.user_id}, doc_id={self.document_id}, algo={self.algorithm})>"
