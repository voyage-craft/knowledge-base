"""Recommendation API endpoints.

Provides personalized document recommendations based on:
- Content similarity (documents with similar embeddings)
- Collaborative filtering (documents popular among similar users)
- Knowledge graph connections (documents sharing entities)
- Hybrid combination of all algorithms

Endpoints:
    GET /api/recommendations - Get personalized recommendations
    GET /api/recommendations/similar/{doc_id} - Get similar documents
    POST /api/recommendations/dismiss/{id} - Dismiss a recommendation
    GET /api/recommendations/trending - Get trending documents
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.document import Document
from app.models.user_activity import UserActivity, UserRecommendation
from app.services.recommendation_service import recommendation_service

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class RecommendationResponse(BaseModel):
    """Response model for a single recommendation."""
    document_id: int
    title: str
    score: float
    algorithm: str
    reason: Optional[str] = None


class RecommendationListResponse(BaseModel):
    """Response model for recommendation list."""
    recommendations: list[RecommendationResponse]
    total: int
    algorithm: str


@router.get("", response_model=RecommendationListResponse)
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50),
    algorithm: str = Query("hybrid", pattern="^(hybrid|content_based|collaborative|graph_based)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get personalized document recommendations for the current user.

    Args:
        limit: Maximum number of recommendations (1-50)
        algorithm: Recommendation algorithm to use

    Returns:
        List of recommended documents with scores and reasons
    """
    recommendations = await recommendation_service.get_user_recommendations(
        user_id=current_user.id,
        limit=limit,
        algorithm=algorithm,
    )

    return RecommendationListResponse(
        recommendations=[RecommendationResponse(**rec) for rec in recommendations],
        total=len(recommendations),
        algorithm=algorithm,
    )


@router.get("/similar/{doc_id}", response_model=list[RecommendationResponse])
async def get_similar_documents(
    doc_id: int,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get documents similar to a specific document.

    Args:
        doc_id: Source document ID
        limit: Maximum number of similar documents

    Returns:
        List of similar documents with similarity scores
    """
    # Verify document exists and user has access
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="文档不存在")

    similar_docs = await recommendation_service.get_similar_documents(
        doc_id=doc_id,
        limit=limit,
    )

    return [RecommendationResponse(**doc) for doc in similar_docs]


@router.post("/dismiss/{recommendation_id}")
async def dismiss_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Dismiss a recommendation so it no longer appears.

    Args:
        recommendation_id: ID of the recommendation to dismiss

    Returns:
        Success message
    """
    result = await db.execute(
        select(UserRecommendation).where(
            UserRecommendation.id == recommendation_id,
            UserRecommendation.user_id == current_user.id,
        )
    )
    recommendation = result.scalar_one_or_none()

    if not recommendation:
        raise HTTPException(status_code=404, detail="推荐不存在")

    recommendation.is_dismissed = 1
    await db.commit()

    return {"message": "推荐已忽略"}


@router.get("/trending", response_model=list[RecommendationResponse])
async def get_trending_documents(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get trending documents across all users.

    Args:
        limit: Maximum number of trending documents
        days: Time window in days to consider

    Returns:
        List of trending documents with popularity scores
    """
    from datetime import datetime, timezone, timedelta

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Get most viewed/edited documents
    trending_result = await db.execute(
        select(
            UserActivity.document_id,
            func.count(UserActivity.id).label("activity_count"),
        )
        .where(UserActivity.document_id.isnot(None))
        .where(UserActivity.activity_type.in_(["view", "edit"]))
        .where(UserActivity.created_at >= cutoff_date)
        .group_by(UserActivity.document_id)
        .order_by(desc("activity_count"))
        .limit(limit * 2)  # Get extra to filter
    )
    trending = trending_result.all()
    if not trending:
        return []

    # Batch fetch documents (fixes N+1 query)
    doc_ids = [doc_id for doc_id, _ in trending]
    docs_result = await db.execute(
        select(Document).where(
            Document.id.in_(doc_ids),
            Document.status != "deleted",
            Document.user_id == current_user.id,
        )
    )
    doc_map = {d.id: d for d in docs_result.scalars().all()}

    recommendations = []
    max_count = trending[0][1] if trending else 1

    for doc_id, activity_count in trending:
        doc = doc_map.get(doc_id)
        if doc:
            recommendations.append(RecommendationResponse(
                document_id=doc.id,
                title=doc.title,
                score=activity_count / max_count,
                algorithm="trending",
                reason=f"Trending with {activity_count} interactions",
            ))
            if len(recommendations) >= limit:
                break

    return recommendations
