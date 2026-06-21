"""Analytics models for usage statistics and content quality assessment.

This module provides models for tracking system usage, content quality,
and generating insights for the analytics dashboard.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class DailyStats(Base):
    """Aggregated daily usage statistics per user.

    Updated daily by a scheduled task that aggregates user_activities.
    """

    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)

    # Document metrics
    documents_created = Column(Integer, default=0)
    documents_edited = Column(Integer, default=0)
    documents_viewed = Column(Integer, default=0)

    # Search metrics
    searches_performed = Column(Integer, default=0)

    # AI metrics
    ai_operations = Column(Integer, default=0)  # summarize, translate, etc.

    # Engagement metrics
    active_minutes = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DailyStats(user={self.user_id}, date={self.date})>"


class ContentQualityScore(Base):
    """Automated content quality assessment for documents.

    Scores are computed using:
    - Rule-based checks (headings, word count, structure)
    - LLM-based evaluation (coherence, accuracy) - sampled periodically
    """

    __tablename__ = "content_quality_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Quality dimensions (0-100 scale)
    completeness_score = Column(Float, default=0.0)  # Has headings, conclusion, etc.
    readability_score = Column(Float, default=0.0)  # Sentence length, vocabulary
    structure_score = Column(Float, default=0.0)  # Heading hierarchy, sections
    freshness_score = Column(Float, default=0.0)  # Days since last edit

    # Overall weighted score
    overall_score = Column(Float, default=0.0)

    # Detailed issues
    issues_json = Column(JSON, nullable=True)  # List of detected issues

    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ContentQualityScore(doc={self.document_id}, overall={self.overall_score})>"


class SearchLog(Base):
    """Search query logging for analytics and optimization.

    Tracks:
    - What users search for
    - Which results they click
    - Search performance metrics
    """

    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(String(500), nullable=False)
    mode = Column(String(20), nullable=False)  # keyword, semantic, hybrid

    # Result metrics
    results_count = Column(Integer, default=0)
    clicked_document_id = Column(Integer, nullable=True)  # Which result was clicked

    # Performance metrics
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_search_log_query", "query"),
        Index("ix_search_log_user_time", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<SearchLog(user={self.user_id}, query={self.query[:30]})>"
