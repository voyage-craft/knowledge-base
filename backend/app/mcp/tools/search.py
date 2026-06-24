"""MCP tool: Search documents in the knowledge base."""

import json
import math
from app.mcp.server import mcp
from app.mcp.auth_context import require_user_id
from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from sqlalchemy import select


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _escape_like(s: str) -> str:
    """Escape SQL LIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@mcp.tool()
async def search_documents(
    query: str,
    top_k: int = 5,
    search_type: str = "semantic",
) -> dict:
    """Search the knowledge base using semantic (embedding) or keyword search.

    Args:
        query: The search query text
        top_k: Maximum number of results (1-20)
        search_type: "semantic" for embedding search, "keyword" for text LIKE search

    Returns matching documents with titles, snippets, and relevance scores.
    """
    if not query.strip():
        return {"error": {"code": "INVALID_INPUT", "message": "Query cannot be empty"}}

    top_k = max(1, min(top_k, 20))
    user_id = require_user_id()

    async with AsyncSessionLocal() as session:
        if search_type == "keyword":
            escaped = _escape_like(query)
            result = await session.execute(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.plain_text.ilike(f"%{escaped}%")
                ).limit(top_k)
            )
            docs = result.scalars().all()
            return {
                "results": [
                    {
                        "document_id": doc.id,
                        "title": doc.title,
                        "snippet": (doc.plain_text or "")[:300],
                        "score": 1.0,
                    }
                    for doc in docs
                ]
            }

        # Semantic search using embeddings
        try:
            from app.services.embedding_service import embedding_service
            query_emb = await embedding_service.embed_query(query)
        except Exception:
            # Fallback to keyword if embedding not available
            escaped = _escape_like(query)
            result = await session.execute(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.plain_text.ilike(f"%{escaped}%")
                ).limit(top_k)
            )
            docs = result.scalars().all()
            return {
                "results": [
                    {
                        "document_id": doc.id,
                        "title": doc.title,
                        "snippet": (doc.plain_text or "")[:300],
                        "score": 1.0,
                    }
                    for doc in docs
                ],
                "note": "Embedding model unavailable, used keyword search",
            }

        # Restrict semantic search to this user's documents
        owned_doc_ids_result = await session.execute(
            select(Document.id).where(Document.user_id == user_id)
        )
        owned_doc_ids = [r[0] for r in owned_doc_ids_result.fetchall()]
        if not owned_doc_ids:
            return {"results": []}

        # Batched vector search to avoid loading all embeddings at once
        BATCH_SIZE = 1000
        all_scored = []
        offset = 0

        try:
            import numpy as np
            query_emb_np = np.array(query_emb)

            while True:
                result = await session.execute(
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.embedding.isnot(None),
                        DocumentChunk.document_id.in_(owned_doc_ids),
                    )
                    .offset(offset)
                    .limit(BATCH_SIZE)
                )
                chunks = result.scalars().all()
                if not chunks:
                    break

                embeddings = []
                for c in chunks:
                    try:
                        emb = json.loads(c.embedding) if isinstance(c.embedding, str) else c.embedding
                        embeddings.append(emb)
                    except Exception:
                        embeddings.append(None)

                # Filter out failed parses
                valid = [(c, e) for c, e in zip(chunks, embeddings) if e is not None]
                if valid:
                    valid_chunks, valid_embs = zip(*valid)
                    embs_np = np.array(valid_embs)
                    norms = np.linalg.norm(embs_np, axis=1)
                    norms[norms == 0] = 1.0
                    scores = (embs_np @ query_emb_np) / (norms * np.linalg.norm(query_emb_np))

                    for chunk, score in zip(valid_chunks, scores):
                        if score > 0.3:
                            all_scored.append((chunk, float(score)))

                offset += BATCH_SIZE

        except ImportError:
            # Fallback: pure Python with batching
            while True:
                result = await session.execute(
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.embedding.isnot(None),
                        DocumentChunk.document_id.in_(owned_doc_ids),
                    )
                    .offset(offset)
                    .limit(BATCH_SIZE)
                )
                chunks = result.scalars().all()
                if not chunks:
                    break

                for chunk in chunks:
                    try:
                        emb = json.loads(chunk.embedding) if isinstance(chunk.embedding, str) else chunk.embedding
                        score = _cosine_similarity(query_emb, emb)
                        if score > 0.3:
                            all_scored.append((chunk, score))
                    except Exception:
                        continue

                offset += BATCH_SIZE

        # Sort by score and take top_k
        all_scored.sort(key=lambda x: x[1], reverse=True)
        top_chunks = all_scored[:top_k]

        # Get document titles
        doc_ids = list(set(c.document_id for c, _ in top_chunks))
        if doc_ids:
            doc_result = await session.execute(select(Document).where(Document.id.in_(doc_ids)))
            doc_map = {d.id: d.title for d in doc_result.scalars().all()}
        else:
            doc_map = {}

        return {
            "results": [
                {
                    "document_id": chunk.document_id,
                    "title": doc_map.get(chunk.document_id, "Unknown"),
                    "chunk_index": chunk.chunk_index,
                    "snippet": (chunk.chunk_text or "")[:300],
                    "score": round(score, 4),
                }
                for chunk, score in top_chunks
            ]
        }
