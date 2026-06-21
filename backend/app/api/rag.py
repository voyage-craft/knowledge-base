"""RAG (Retrieval-Augmented Generation) API endpoints.

Provides document embedding generation and similarity search.
"""

import json
import logging

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from pydantic import BaseModel

from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.chunking import chunk_text
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


class EmbedResponse(BaseModel):
    document_id: int
    chunks_created: int


class SearchResult(BaseModel):
    document_id: int
    document_title: str
    chunk_index: int
    chunk_text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str


class StatusResponse(BaseModel):
    total_documents: int
    embedded_documents: int
    total_chunks: int


@router.post("/embed/{document_id}", response_model=EmbedResponse)
async def embed_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Generate embeddings for a single document (runs in background)."""
    # Verify document ownership
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="文档不存在")

    background_tasks.add_task(_embed_document_task, document_id, current_user.id)
    return EmbedResponse(document_id=document_id, chunks_created=0)


@router.post("/embed-batch")
async def embed_batch(
    data: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Generate embeddings for all user documents."""
    result = await db.execute(
        select(Document.id).where(
            Document.user_id == current_user.id,
            Document.status != "deleted",
        )
    )
    doc_ids = [row[0] for row in result.all()]

    for doc_id in doc_ids:
        background_tasks.add_task(_embed_document_task, doc_id, current_user.id)

    return {"message": f"已提交 {len(doc_ids)} 篇文档进行嵌入处理"}


@router.delete("/embeddings/{document_id}")
async def delete_embeddings(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Delete all embeddings for a document."""
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.user_id == current_user.id,
        )
    )
    await db.commit()
    return {"message": "嵌入数据已删除"}


@router.get("/status", response_model=StatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get embedding status for the current user."""
    # Total non-deleted documents
    total_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id,
            Document.status != "deleted",
        )
    )
    total_documents = total_result.scalar() or 0

    # Documents with embeddings
    embedded_result = await db.execute(
        select(func.count(func.distinct(DocumentChunk.document_id))).where(
            DocumentChunk.user_id == current_user.id,
        )
    )
    embedded_documents = embedded_result.scalar() or 0

    # Total chunks
    chunks_result = await db.execute(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.user_id == current_user.id,
        )
    )
    total_chunks = chunks_result.scalar() or 0

    return StatusResponse(
        total_documents=total_documents,
        embedded_documents=embedded_documents,
        total_chunks=total_chunks,
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Semantic search across user's document chunks."""
    # Embed the query
    try:
        query_embedding = await embedding_service.embed_query(q)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Load all user's chunks with embeddings
    result = await db.execute(
        select(DocumentChunk).where(
            DocumentChunk.user_id == current_user.id,
            DocumentChunk.embedding.isnot(None),
        )
    )
    chunks = result.scalars().all()

    if not chunks:
        return SearchResponse(results=[], query=q)

    # Compute similarities
    scored: list[tuple[DocumentChunk, float]] = []

    if HAS_NUMPY:
        # Optimized numpy batch computation
        embeddings_list = []
        valid_chunks = []

        for chunk in chunks:
            try:
                emb = json.loads(chunk.embedding) if isinstance(chunk.embedding, str) else chunk.embedding
                if emb and len(emb) > 0:
                    embeddings_list.append(emb)
                    valid_chunks.append(chunk)
            except (json.JSONDecodeError, TypeError):
                continue

        if not embeddings_list:
            return SearchResponse(results=[], query=q)

        # Convert to numpy arrays for batch computation
        embeddings_matrix = np.array(embeddings_list)
        query_vec = np.array(query_embedding)

        # Batch cosine similarity: dot product / (norm * norm)
        norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
        normalized_embeddings = embeddings_matrix / norms

        # Normalize query
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return SearchResponse(results=[], query=q)
        normalized_query = query_vec / query_norm

        # Compute similarities
        scores = normalized_embeddings @ normalized_query

        # Filter by threshold and get top_k
        mask = scores >= threshold
        filtered_indices = np.where(mask)[0]
        filtered_scores = scores[mask]

        # Sort by score descending
        sorted_indices = np.argsort(filtered_scores)[::-1][:top_k]

        # Build results
        scored = [(valid_chunks[filtered_indices[i]], float(filtered_scores[i])) for i in sorted_indices]
    else:
        # Fallback: pure Python implementation
        from app.services.embedding_service import cosine_similarity

        for chunk in chunks:
            try:
                emb = json.loads(chunk.embedding) if isinstance(chunk.embedding, str) else chunk.embedding
                score = cosine_similarity(query_embedding, emb)
                if score >= threshold:
                    scored.append((chunk, score))
            except (json.JSONDecodeError, TypeError):
                continue

        # Sort by score descending, take top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]

    # Fetch document titles
    doc_ids = list(set(chunk.document_id for chunk, _ in scored))
    if doc_ids:
        doc_result = await db.execute(
            select(Document.id, Document.title).where(Document.id.in_(doc_ids))
        )
        title_map = {row[0]: row[1] for row in doc_result.all()}
    else:
        title_map = {}

    results = [
        SearchResult(
            document_id=chunk.document_id,
            document_title=title_map.get(chunk.document_id, "未知文档"),
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text[:500],
            score=round(score, 4),
        )
        for chunk, score in scored
    ]

    return SearchResponse(results=results, query=q)


async def _embed_document_task(document_id: int, user_id: int):
    """Background task: chunk and embed a single document."""
    from app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if not doc or doc.user_id != user_id:
                return

            # Get text content
            text = doc.plain_text or ""
            if not text.strip():
                # Try extracting from content_json
                if doc.content_json:
                    import re
                    content = doc.content_json if isinstance(doc.content_json, str) else json.dumps(doc.content_json)
                    text = re.sub(r'<[^>]+>', '', content)

            if not text.strip():
                return

            # Delete old chunks
            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.user_id == user_id,
                )
            )

            # Chunk the text
            chunks = chunk_text(text)
            if not chunks:
                await db.commit()
                return

            # Generate embeddings
            texts = [c["chunk_text"] for c in chunks]
            try:
                embeddings = await embedding_service.embed(texts)
            except RuntimeError as e:
                logger.error("Embedding failed for doc %d: %s", document_id, e)
                await db.commit()
                return

            # Store chunks with embeddings
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk["chunk_text"],
                    embedding=json.dumps(emb),
                    user_id=user_id,
                )
                db.add(db_chunk)

            await db.commit()
            logger.info("Embedded doc %d: %d chunks", document_id, len(chunks))

    except Exception as e:
        logger.error("Embed task failed for doc %d: %s", document_id, e)
