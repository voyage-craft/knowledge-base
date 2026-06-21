from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.core.database import get_db, AsyncSessionLocal
from app.models.graph import GraphNode, GraphEdge
from app.models.document import Document
from app.models.user import User
from app.schemas.graph import (
    GraphDataResponse, GraphNodeResponse, GraphEdgeResponse,
    DocumentGraphResponse, BuildGraphResponse,
)
from app.api.auth import get_current_user_dep
from app.services.ai_pipeline import ai_pipeline
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Module-level lock: only one graph build per user at a time
_build_locks: dict[int, asyncio.Lock] = {}


@router.get("", response_model=GraphDataResponse)
async def get_graph(
    document_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get user's complete knowledge graph, optionally filtered by document."""
    node_query = select(GraphNode).where(GraphNode.user_id == current_user.id)
    edge_query = select(GraphEdge).where(GraphEdge.user_id == current_user.id)

    if document_id:
        # Get nodes linked to this document and all edges between them
        doc_nodes_q = select(GraphNode.id).where(
            GraphNode.user_id == current_user.id,
            GraphNode.document_id == document_id,
        )
        doc_node_ids_result = await db.execute(doc_nodes_q)
        doc_node_ids = {row[0] for row in doc_node_ids_result}

        if not doc_node_ids:
            return GraphDataResponse(nodes=[], edges=[])

        node_query = select(GraphNode).where(GraphNode.id.in_(doc_node_ids))
        edge_query = select(GraphEdge).where(
            GraphEdge.user_id == current_user.id,
            GraphEdge.source_id.in_(doc_node_ids),
            GraphEdge.target_id.in_(doc_node_ids),
        )

    nodes_result = await db.execute(node_query)
    edges_result = await db.execute(edge_query)

    nodes = [GraphNodeResponse.model_validate(n) for n in nodes_result.scalars().all()]
    edges = [GraphEdgeResponse.model_validate(e) for e in edges_result.scalars().all()]

    return GraphDataResponse(nodes=nodes, edges=edges)


@router.get("/document/{doc_id}", response_model=DocumentGraphResponse)
async def get_document_graph(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get graph entities and relationships for a specific document."""
    # Verify document ownership
    doc_result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Get all nodes linked to this document
    node_result = await db.execute(
        select(GraphNode).where(
            GraphNode.user_id == current_user.id,
            GraphNode.document_id == doc_id,
        )
    )
    nodes = node_result.scalars().all()
    node_ids = {n.id for n in nodes}

    # Find the document node
    document_node = next((n for n in nodes if n.node_type == "document"), None)

    # Get edges between these nodes
    if node_ids:
        edge_result = await db.execute(
            select(GraphEdge).where(
                GraphEdge.user_id == current_user.id,
                GraphEdge.source_id.in_(node_ids),
                GraphEdge.target_id.in_(node_ids),
            )
        )
        edges = edge_result.scalars().all()
    else:
        edges = []

    return DocumentGraphResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
        document_node=GraphNodeResponse.model_validate(document_node) if document_node else None,
    )


async def _build_graph_for_user(user_id: int):
    """Background task: analyze all documents and build the full knowledge graph."""
    # Acquire per-user lock to prevent concurrent builds
    if user_id not in _build_locks:
        _build_locks[user_id] = asyncio.Lock()

    if _build_locks[user_id].locked():
        logger.info("Graph build already in progress for user %d, skipping", user_id)
        return

    async with _build_locks[user_id]:
        async with AsyncSessionLocal() as db:
            # Fetch all non-deleted documents
            result = await db.execute(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.status != "deleted",
                )
            )
            documents = result.scalars().all()

            if not documents:
                logger.info("No documents to build graph for user %d", user_id)
                return

            # Delete existing graph data for this user
            await db.execute(delete(GraphEdge).where(GraphEdge.user_id == user_id))
            await db.execute(delete(GraphNode).where(GraphNode.user_id == user_id))
            await db.commit()

            nodes_created = 0
            edges_created = 0

            # Label→node cache to deduplicate
            node_cache: dict[tuple[str, str], GraphNode] = {}

            for doc in documents:
                # Extract text for analysis
                text = doc.plain_text or ""
                if not text and doc.content_json:
                    # Try to extract plain text from TipTap JSON
                    try:
                        import json
                        content = doc.content_json if isinstance(doc.content_json, dict) else json.loads(doc.content_json)
                        parts = []
                        for node in content.get("content", []):
                            if "content" in node:
                                for inline in node["content"]:
                                    if inline.get("type") == "text":
                                        parts.append(inline.get("text", ""))
                            parts.append("")  # paragraph break
                        text = "\n".join(parts)
                    except Exception:
                        text = doc.title

                if not text.strip():
                    text = doc.title

                # Create document node
                doc_node = GraphNode(
                    user_id=user_id,
                    node_type="document",
                    label=doc.title,
                    document_id=doc.id,
                    embedding_text=text[:500],
                )
                db.add(doc_node)
                await db.flush()
                nodes_created += 1

                # AI extraction
                try:
                    extraction = await ai_pipeline.extract_graph_entities(text, doc.title)
                except Exception as e:
                    logger.error("Graph extraction failed for doc %d: %s", doc.id, e)
                    continue

                # Create entity nodes
                for entity in extraction.get("entities", []):
                    label = entity.get("label", "").strip()
                    etype = entity.get("type", "term")
                    if not label:
                        continue

                    cache_key = (label.lower(), "entity")
                    if cache_key not in node_cache:
                        node = GraphNode(
                            user_id=user_id,
                            node_type="entity",
                            label=label,
                            description=entity.get("description"),
                            document_id=doc.id,
                            metadata_json={"entity_type": etype},
                        )
                        db.add(node)
                        await db.flush()
                        node_cache[cache_key] = node
                        nodes_created += 1

                    # Edge: document → entity
                    target = node_cache[cache_key]
                    edge = GraphEdge(
                        user_id=user_id,
                        source_id=doc_node.id,
                        target_id=target.id,
                        edge_type="contains_entity",
                    )
                    db.add(edge)
                    edges_created += 1

                # Create concept nodes
                for concept in extraction.get("concepts", []):
                    label = concept.get("label", "").strip()
                    if not label:
                        continue

                    cache_key = (label.lower(), "concept")
                    if cache_key not in node_cache:
                        node = GraphNode(
                            user_id=user_id,
                            node_type="concept",
                            label=label,
                            description=concept.get("description"),
                            document_id=doc.id,
                        )
                        db.add(node)
                        await db.flush()
                        node_cache[cache_key] = node
                        nodes_created += 1

                    # Edge: document → concept
                    target = node_cache[cache_key]
                    edge = GraphEdge(
                        user_id=user_id,
                        source_id=doc_node.id,
                        target_id=target.id,
                        edge_type="contains_entity",
                    )
                    db.add(edge)
                    edges_created += 1

                # Create relationship edges
                for rel in extraction.get("relationships", []):
                    source_label = rel.get("source", "").strip().lower()
                    target_label = rel.get("target", "").strip().lower()
                    rel_type = rel.get("type", "related_to")
                    if not source_label or not target_label:
                        continue

                    source_node = None
                    target_node = None
                    for (lbl, _), node in node_cache.items():
                        if lbl == source_label:
                            source_node = node
                        if lbl == target_label:
                            target_node = node

                    if source_node and target_node:
                        edge = GraphEdge(
                            user_id=user_id,
                            source_id=source_node.id,
                            target_id=target_node.id,
                            edge_type=rel_type,
                            description=rel.get("description"),
                        )
                        db.add(edge)
                        edges_created += 1

            await db.commit()
        logger.info("Graph build complete for user %d: %d nodes, %d edges", user_id, nodes_created, edges_created)


@router.post("/build", response_model=BuildGraphResponse)
async def build_graph(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Trigger AI-powered knowledge graph build for all documents (runs in background)."""
    # Efficient count using func.count() instead of loading all documents
    count_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id,
            Document.status != "deleted",
        )
    )
    doc_count = count_result.scalar() or 0

    # Check if build is already in progress
    if current_user.id in _build_locks and _build_locks[current_user.id].locked():
        return BuildGraphResponse(
            message="图谱正在构建中，请稍候",
            nodes_created=0,
            edges_created=0,
        )

    background_tasks.add_task(_build_graph_for_user, current_user.id)

    return BuildGraphResponse(
        message=f"图谱构建已启动，共 {doc_count} 篇文档，正在后台处理",
        nodes_created=0,
        edges_created=0,
    )


@router.post("/document/{doc_id}/analyze", response_model=DocumentGraphResponse)
async def analyze_document_graph(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """AI analyze a single document and update its graph nodes."""
    # Verify document ownership
    doc_result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Remove old graph nodes for this document
    old_nodes_result = await db.execute(
        select(GraphNode).where(
            GraphNode.user_id == current_user.id,
            GraphNode.document_id == doc_id,
        )
    )
    old_nodes = old_nodes_result.scalars().all()
    old_node_ids = {n.id for n in old_nodes}

    if old_node_ids:
        await db.execute(
            delete(GraphEdge).where(
                GraphEdge.user_id == current_user.id,
                GraphEdge.source_id.in_(old_node_ids),
            )
        )
        await db.execute(
            delete(GraphEdge).where(
                GraphEdge.user_id == current_user.id,
                GraphEdge.target_id.in_(old_node_ids),
            )
        )
        await db.execute(delete(GraphNode).where(GraphNode.id.in_(old_node_ids)))
        await db.flush()

    # Extract text
    text = doc.plain_text or doc.title

    # AI extraction
    extraction = await ai_pipeline.extract_graph_entities(text, doc.title)

    # Create document node
    doc_node = GraphNode(
        user_id=current_user.id,
        node_type="document",
        label=doc.title,
        document_id=doc.id,
        embedding_text=text[:500],
    )
    db.add(doc_node)
    await db.flush()

    new_nodes = [doc_node]

    # Create entity nodes
    for entity in extraction.get("entities", []):
        label = entity.get("label", "").strip()
        if not label:
            continue
        # Check if a node with this label already exists for this user
        existing = await db.execute(
            select(GraphNode).where(
                GraphNode.user_id == current_user.id,
                GraphNode.node_type == "entity",
                GraphNode.label == label,
            )
        )
        node = existing.scalar_one_or_none()
        if not node:
            node = GraphNode(
                user_id=current_user.id,
                node_type="entity",
                label=label,
                description=entity.get("description"),
                document_id=doc.id,
                metadata_json={"entity_type": entity.get("type", "term")},
            )
            db.add(node)
            await db.flush()

        new_nodes.append(node)

        edge = GraphEdge(
            user_id=current_user.id,
            source_id=doc_node.id,
            target_id=node.id,
            edge_type="contains_entity",
        )
        db.add(edge)

    # Create concept nodes
    for concept in extraction.get("concepts", []):
        label = concept.get("label", "").strip()
        if not label:
            continue
        existing = await db.execute(
            select(GraphNode).where(
                GraphNode.user_id == current_user.id,
                GraphNode.node_type == "concept",
                GraphNode.label == label,
            )
        )
        node = existing.scalar_one_or_none()
        if not node:
            node = GraphNode(
                user_id=current_user.id,
                node_type="concept",
                label=label,
                description=concept.get("description"),
                document_id=doc.id,
            )
            db.add(node)
            await db.flush()

        new_nodes.append(node)

        edge = GraphEdge(
            user_id=current_user.id,
            source_id=doc_node.id,
            target_id=node.id,
            edge_type="contains_entity",
        )
        db.add(edge)

    await db.commit()

    # Fetch the updated graph for this document
    node_ids = {n.id for n in new_nodes}
    edge_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.user_id == current_user.id,
            GraphEdge.source_id.in_(node_ids),
            GraphEdge.target_id.in_(node_ids),
        )
    )
    edges = edge_result.scalars().all()

    return DocumentGraphResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in new_nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
        document_node=GraphNodeResponse.model_validate(doc_node),
    )


@router.delete("/node/{node_id}")
async def delete_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Delete a graph node and its edges."""
    result = await db.execute(
        select(GraphNode).where(GraphNode.id == node_id, GraphNode.user_id == current_user.id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # Delete related edges (filtered by user_id for safety)
    await db.execute(
        delete(GraphEdge).where(
            GraphEdge.user_id == current_user.id,
            (GraphEdge.source_id == node_id) | (GraphEdge.target_id == node_id)
        )
    )
    await db.delete(node)
    await db.commit()

    return {"message": "节点已删除"}
