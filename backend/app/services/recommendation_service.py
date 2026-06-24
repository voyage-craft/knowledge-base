"""Intelligent recommendation service for the knowledge base system.

This module provides multiple recommendation algorithms:
1. Content-based: Using document embeddings for similarity
2. Collaborative filtering: Based on user behavior patterns
3. Graph-based: Leveraging knowledge graph connections
4. Hybrid: Weighted combination of all algorithms

Usage:
    from app.services.recommendation_service import recommendation_service

    # Get personalized recommendations for a user
    recommendations = await recommendation_service.get_user_recommendations(user_id=1, limit=10)

    # Get similar documents
    similar_docs = await recommendation_service.get_similar_documents(doc_id=42, limit=5)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user_activity import UserActivity, DocumentRelation, UserRecommendation
from app.models.graph import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class RecommendationService:
    """Provides intelligent document recommendations using multiple algorithms."""

    # Algorithm weights for hybrid scoring
    WEIGHTS = {
        "content_similarity": 0.4,
        "collaborative": 0.3,
        "graph_based": 0.2,
        "recency": 0.1,
    }

    async def get_user_recommendations(
        self,
        user_id: int,
        limit: int = 10,
        algorithm: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Get personalized document recommendations for a user.

        Args:
            user_id: Target user ID
            limit: Maximum number of recommendations
            algorithm: Algorithm to use (hybrid, content_based, collaborative, graph_based)

        Returns:
            List of recommendation dicts with document info and scores
        """
        async with get_session() as db:
            if algorithm == "hybrid":
                return await self._hybrid_recommendations(db, user_id, limit)
            elif algorithm == "content_based":
                return await self._content_based_recommendations(db, user_id, limit)
            elif algorithm == "collaborative":
                return await self._collaborative_recommendations(db, user_id, limit)
            elif algorithm == "graph_based":
                return await self._graph_based_recommendations(db, user_id, limit)
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")

    async def get_similar_documents(
        self,
        doc_id: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get documents similar to a specific document.

        Args:
            doc_id: Source document ID
            limit: Maximum number of similar documents

        Returns:
            List of similar document dicts with similarity scores
        """
        async with get_session() as db:
            # Get document
            doc = await db.get(Document, doc_id)
            if not doc:
                return []

            # Get document chunks with embeddings
            chunks_result = await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc_id)
                .where(DocumentChunk.embedding.isnot(None))
            )
            chunks = chunks_result.scalars().all()

            if not chunks:
                return []

            # Find similar documents using stored relations
            relations_result = await db.execute(
                select(DocumentRelation)
                .where(DocumentRelation.source_doc_id == doc_id)
                .where(DocumentRelation.relation_type == "similar_content")
                .order_by(desc(DocumentRelation.score))
                .limit(limit)
            )
            relations = relations_result.scalars().all()

            # Get document details (batch fetch to avoid N+1)
            target_doc_ids = [rel.target_doc_id for rel in relations]
            if target_doc_ids:
                doc_result = await db.execute(
                    select(Document).where(Document.id.in_(target_doc_ids))
                )
                docs_by_id = {d.id: d for d in doc_result.scalars().all()}
            else:
                docs_by_id = {}

            similar_docs = []
            for rel in relations:
                target_doc = docs_by_id.get(rel.target_doc_id)
                if target_doc and target_doc.status != "deleted":
                    similar_docs.append({
                        "document_id": target_doc.id,
                        "title": target_doc.title,
                        "score": rel.score / 1000.0,  # Normalize to 0-1
                        "relation_type": rel.relation_type,
                    })

            return similar_docs

    async def _hybrid_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Combine multiple algorithms for hybrid recommendations."""
        # Get recommendations from each algorithm
        content_recs = await self._content_based_recommendations(db, user_id, limit * 2)
        collab_recs = await self._collaborative_recommendations(db, user_id, limit * 2)
        graph_recs = await self._graph_based_recommendations(db, user_id, limit * 2)

        # Merge and weight scores
        doc_scores: dict[int, dict[str, Any]] = {}

        for rec in content_recs:
            doc_id = rec["document_id"]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = rec.copy()
                doc_scores[doc_id]["score"] = 0
            doc_scores[doc_id]["score"] += rec["score"] * self.WEIGHTS["content_similarity"]

        for rec in collab_recs:
            doc_id = rec["document_id"]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = rec.copy()
                doc_scores[doc_id]["score"] = 0
            doc_scores[doc_id]["score"] += rec["score"] * self.WEIGHTS["collaborative"]

        for rec in graph_recs:
            doc_id = rec["document_id"]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = rec.copy()
                doc_scores[doc_id]["score"] = 0
            doc_scores[doc_id]["score"] += rec["score"] * self.WEIGHTS["graph_based"]

        # Sort by score and return top N
        sorted_recs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        return sorted_recs[:limit]

    async def _content_based_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Find documents similar to user's recently viewed/edited documents."""
        # Get user's recent activity
        recent_activity = await db.execute(
            select(UserActivity.document_id)
            .where(UserActivity.user_id == user_id)
            .where(UserActivity.document_id.isnot(None))
            .where(UserActivity.activity_type.in_(["view", "edit"]))
            .order_by(desc(UserActivity.created_at))
            .limit(10)
        )
        recent_doc_ids = [row[0] for row in recent_activity.all()]

        if not recent_doc_ids:
            return []

        # Find similar documents using stored relations
        similar_docs_result = await db.execute(
            select(DocumentRelation)
            .where(DocumentRelation.source_doc_id.in_(recent_doc_ids))
            .where(DocumentRelation.relation_type == "similar_content")
            .order_by(desc(DocumentRelation.score))
            .limit(limit * 2)
        )
        similar_relations = similar_docs_result.scalars().all()

        # Filter out documents user already knows about
        known_doc_ids = set(recent_doc_ids)
        recommendations = []
        seen_doc_ids = set()

        # Batch fetch all candidate documents to avoid N+1
        candidate_doc_ids = [
            rel.target_doc_id for rel in similar_relations
            if rel.target_doc_id not in known_doc_ids and rel.target_doc_id not in seen_doc_ids
        ]
        if candidate_doc_ids:
            doc_result = await db.execute(
                select(Document).where(Document.id.in_(candidate_doc_ids))
            )
            docs_by_id = {d.id: d for d in doc_result.scalars().all()}
        else:
            docs_by_id = {}

        for rel in similar_relations:
            if rel.target_doc_id not in known_doc_ids and rel.target_doc_id not in seen_doc_ids:
                target_doc = docs_by_id.get(rel.target_doc_id)
                if target_doc and target_doc.status != "deleted":
                    recommendations.append({
                        "document_id": target_doc.id,
                        "title": target_doc.title,
                        "score": rel.score / 1000.0,
                        "algorithm": "content_based",
                        "reason": "Similar to documents you've viewed",
                    })
                    seen_doc_ids.add(rel.target_doc_id)

                    if len(recommendations) >= limit:
                        break

        return recommendations

    async def _collaborative_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Find documents popular among users with similar behavior."""
        # Get user's document interaction set
        user_docs_result = await db.execute(
            select(UserActivity.document_id)
            .where(UserActivity.user_id == user_id)
            .where(UserActivity.document_id.isnot(None))
            .where(UserActivity.activity_type.in_(["view", "edit"]))
        )
        user_doc_ids = set(row[0] for row in user_docs_result.all())

        if not user_doc_ids:
            return []

        # Find users who interacted with similar documents
        similar_users_result = await db.execute(
            select(UserActivity.user_id, func.count(UserActivity.document_id).label("overlap"))
            .where(UserActivity.document_id.in_(list(user_doc_ids)))
            .where(UserActivity.user_id != user_id)
            .where(UserActivity.activity_type.in_(["view", "edit"]))
            .group_by(UserActivity.user_id)
            .order_by(desc("overlap"))
            .limit(20)
        )
        similar_users = similar_users_result.all()

        if not similar_users:
            return []

        similar_user_ids = [row[0] for row in similar_users]

        # Get documents these similar users viewed that target user hasn't
        collab_docs_result = await db.execute(
            select(
                UserActivity.document_id,
                func.count(UserActivity.user_id).label("popularity"),
            )
            .where(UserActivity.user_id.in_(similar_user_ids))
            .where(UserActivity.document_id.notin_(list(user_doc_ids)))
            .where(UserActivity.activity_type.in_(["view", "edit"]))
            .group_by(UserActivity.document_id)
            .order_by(desc("popularity"))
            .limit(limit * 2)
        )
        collab_docs = collab_docs_result.all()

        recommendations = []
        max_popularity = collab_docs[0][1] if collab_docs else 1

        # Batch fetch all documents to avoid N+1
        collab_doc_ids = [doc_id for doc_id, _ in collab_docs]
        if collab_doc_ids:
            doc_result = await db.execute(
                select(Document).where(Document.id.in_(collab_doc_ids))
            )
            docs_by_id = {d.id: d for d in doc_result.scalars().all()}
        else:
            docs_by_id = {}

        for doc_id, popularity in collab_docs:
            doc = docs_by_id.get(doc_id)
            if doc and doc.status != "deleted":
                recommendations.append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "score": popularity / max_popularity,
                    "algorithm": "collaborative",
                    "reason": "Popular among similar users",
                })

                if len(recommendations) >= limit:
                    break

        return recommendations

    async def _graph_based_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Find documents connected via knowledge graph entities."""
        # Get entities from user's documents
        user_docs_result = await db.execute(
            select(UserActivity.document_id)
            .where(UserActivity.user_id == user_id)
            .where(UserActivity.document_id.isnot(None))
            .where(UserActivity.activity_type.in_(["view", "edit"]))
            .order_by(desc(UserActivity.created_at))
            .limit(10)
        )
        user_doc_ids = [row[0] for row in user_docs_result.all()]

        if not user_doc_ids:
            return []

        # Find entities mentioned in user's documents
        entities_result = await db.execute(
            select(GraphNode.id, GraphNode.label)
            .where(GraphNode.document_id.in_(user_doc_ids))
            .limit(50)
        )
        entities = entities_result.all()

        if not entities:
            return []

        entity_ids = [row[0] for row in entities]

        # Find other documents mentioning these entities
        related_docs_result = await db.execute(
            select(
                GraphNode.document_id,
                func.count(GraphNode.id).label("entity_overlap"),
            )
            .where(GraphNode.id.in_(entity_ids))
            .where(GraphNode.document_id.notin_(user_doc_ids))
            .where(GraphNode.document_id.isnot(None))
            .group_by(GraphNode.document_id)
            .order_by(desc("entity_overlap"))
            .limit(limit * 2)
        )
        related_docs = related_docs_result.all()

        recommendations = []
        max_overlap = related_docs[0][1] if related_docs else 1

        # Batch fetch all documents to avoid N+1
        graph_doc_ids = [doc_id for doc_id, _ in related_docs]
        if graph_doc_ids:
            doc_result = await db.execute(
                select(Document).where(Document.id.in_(graph_doc_ids))
            )
            docs_by_id = {d.id: d for d in doc_result.scalars().all()}
        else:
            docs_by_id = {}

        for doc_id, overlap in related_docs:
            doc = docs_by_id.get(doc_id)
            if doc and doc.status != "deleted":
                # Get entity names for reason
                entity_names = [row[1] for row in entities[:3]]

                recommendations.append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "score": overlap / max_overlap,
                    "algorithm": "graph_based",
                    "reason": f"Related to: {', '.join(entity_names)}",
                })

                if len(recommendations) >= limit:
                    break

        return recommendations

    async def update_document_relations(self, doc_id: int) -> None:
        """Update similarity relations for a document.

        This should be called after document content changes.
        It computes content-based similarities with other documents.
        """
        async with get_session() as db:
            # Get document chunks with embeddings
            chunks_result = await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc_id)
                .where(DocumentChunk.embedding.isnot(None))
            )
            chunks = chunks_result.scalars().all()

            if not chunks:
                return

            # Compute average embedding for the document
            embeddings = []
            for chunk in chunks:
                try:
                    emb = json.loads(chunk.embedding) if isinstance(chunk.embedding, str) else chunk.embedding
                    if emb:
                        embeddings.append(emb)
                except (json.JSONDecodeError, TypeError):
                    continue

            if not embeddings:
                return

            # Find similar documents using cosine similarity
            # For now, we'll use a simple approach - in production, use pgvector
            all_docs_result = await db.execute(
                select(Document.id)
                .where(Document.id != doc_id)
                .where(Document.status != "deleted")
                .limit(100)
            )
            other_doc_ids = [row[0] for row in all_docs_result.all()]

            # Delete old relations for this document
            from sqlalchemy import delete
            await db.execute(
                delete(DocumentRelation).where(DocumentRelation.source_doc_id == doc_id)
            )

            # Batch fetch chunks for all other documents to avoid N+1
            if other_doc_ids:
                all_chunks_result = await db.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id.in_(other_doc_ids))
                    .where(DocumentChunk.embedding.isnot(None))
                )
                all_chunks: dict[int, list] = {}
                for chunk in all_chunks_result.scalars().all():
                    all_chunks.setdefault(chunk.document_id, []).append(chunk)
            else:
                all_chunks = {}

            # Compute similarities with other documents
            for other_doc_id in other_doc_ids:
                other_chunks = all_chunks.get(other_doc_id, [])

                if not other_chunks:
                    continue

                # Compute similarity (simplified - in production use pgvector)
                other_embeddings = []
                for chunk in other_chunks:
                    try:
                        emb = json.loads(chunk.embedding) if isinstance(chunk.embedding, str) else chunk.embedding
                        if emb:
                            other_embeddings.append(emb)
                    except (json.JSONDecodeError, TypeError):
                        continue

                if not other_embeddings:
                    continue

                # Simple average similarity
                similarity = self._compute_document_similarity(embeddings, other_embeddings)

                if similarity > 0.3:  # Threshold
                    relation = DocumentRelation(
                        source_doc_id=doc_id,
                        target_doc_id=other_doc_id,
                        relation_type="similar_content",
                        score=int(similarity * 1000),
                    )
                    db.add(relation)

            await db.commit()
            logger.info("Updated document relations for doc %d", doc_id)

    def _compute_document_similarity(
        self,
        embeddings1: list[list[float]],
        embeddings2: list[list[float]],
    ) -> float:
        """Compute similarity between two sets of embeddings.

        Uses average cosine similarity between all pairs.
        """
        if not embeddings1 or not embeddings2:
            return 0.0

        # Simple implementation - in production use numpy
        total_similarity = 0.0
        count = 0

        for emb1 in embeddings1[:5]:  # Limit for performance
            for emb2 in embeddings2[:5]:
                similarity = self._cosine_similarity(emb1, emb2)
                total_similarity += similarity
                count += 1

        return total_similarity / count if count > 0 else 0.0

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# Global recommendation service instance
recommendation_service = RecommendationService()
