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
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Module-level lock: only one graph build per user at a time
_build_locks: dict[int, asyncio.Lock] = {}

# Build progress tracking: user_id -> {status, current, total, started_at}
_build_progress: dict[int, dict] = {}


def _update_progress(user_id: int, **kwargs):
    """Update build progress for a user."""
    if user_id not in _build_progress:
        _build_progress[user_id] = {"status": "idle", "current": 0, "total": 0}
    _build_progress[user_id].update(kwargs)


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
    """Background task: analyze all documents and build the full knowledge graph.
    Uses concurrent LLM calls and batch DB operations for performance."""
    if user_id not in _build_locks:
        _build_locks[user_id] = asyncio.Lock()

    if _build_locks[user_id].locked():
        logger.info("Graph build already in progress for user %d, skipping", user_id)
        return

    async with _build_locks[user_id]:
        _update_progress(user_id, status="building", current=0, total=0, started_at=time.time())

        try:
            async with AsyncSessionLocal() as db:
                # Only load needed columns to avoid fetching large content_json/tags
                result = await db.execute(
                    select(Document.id, Document.title, Document.plain_text, Document.content_json).where(
                        Document.user_id == user_id,
                        Document.status != "deleted",
                    )
                )
                rows = result.all()

                if not rows:
                    _update_progress(user_id, status="idle", current=0, total=0)
                    return

                total = len(rows)
                _update_progress(user_id, status="building", current=0, total=total)

                # Delete existing graph data
                await db.execute(delete(GraphEdge).where(GraphEdge.user_id == user_id))
                await db.execute(delete(GraphNode).where(GraphNode.user_id == user_id))
                await db.commit()

                # ── Phase 1: Concurrent LLM extraction ──
                semaphore = asyncio.Semaphore(5)
                completed_count = 0  # Track progress during Phase 1
                failed_count = 0

                async def extract_one(doc_id, doc_title, doc_plain_text, doc_content_json):
                    nonlocal completed_count, failed_count
                    text = doc_plain_text or ""
                    if not text and doc_content_json:
                        try:
                            import json
                            content = doc_content_json if isinstance(doc_content_json, dict) else json.loads(doc_content_json)
                            parts = []
                            for node in content.get("content", []):
                                if "content" in node:
                                    for inline in node["content"]:
                                        if inline.get("type") == "text":
                                            parts.append(inline.get("text", ""))
                                parts.append("")
                            text = "\n".join(parts)
                        except Exception:
                            text = doc_title
                    if not text.strip():
                        text = doc_title

                    async with semaphore:
                        try:
                            extraction = await asyncio.wait_for(
                                ai_pipeline.extract_graph_entities(text, doc_title),
                                timeout=120,
                            )
                            return doc_id, doc_title, text, extraction
                        except asyncio.TimeoutError:
                            logger.error("Graph extraction timed out for doc %d", doc_id)
                            failed_count += 1
                            return doc_id, doc_title, text, None
                        except Exception as e:
                            logger.error("Graph extraction failed for doc %d: %s", doc_id, e)
                            failed_count += 1
                            return doc_id, doc_title, text, None
                        finally:
                            completed_count += 1
                            _update_progress(user_id, current=completed_count, total=total, phase="extracting")

                results = await asyncio.gather(*[extract_one(*r) for r in rows])

                # ── Phase 2: Batch insert all nodes and edges ──
                _update_progress(user_id, phase="saving", current=0, total=total)

                node_cache: dict[str, GraphNode] = {}  # lowercase label → node
                doc_node_cache: dict[str, GraphNode] = {}  # lowercase title → doc node
                nodes_created = 0
                edges_created = 0
                pending_edges: list[dict] = []

                for doc_id, doc_title, text, extraction in results:
                    # Create document node
                    doc_node = GraphNode(
                        user_id=user_id,
                        node_type="document",
                        label=doc_title,
                        document_id=doc_id,
                        embedding_text=text[:500],
                    )
                    db.add(doc_node)
                    doc_node_cache[doc_title.lower()] = doc_node
                    nodes_created += 1

                    if not extraction:
                        continue

                    # Create entity nodes
                    for entity in extraction.get("entities", []):
                        label = entity.get("label", "").strip()
                        etype = entity.get("type", "term")
                        if not label:
                            continue

                        cache_key = label.lower()
                        if cache_key not in node_cache:
                            node = GraphNode(
                                user_id=user_id,
                                node_type="entity",
                                label=label,
                                description=entity.get("description"),
                                document_id=doc_id,
                                metadata_json={"entity_type": etype},
                            )
                            db.add(node)
                            node_cache[cache_key] = node
                            nodes_created += 1

                        # Queue edge: document → entity
                        pending_edges.append({
                            "user_id": user_id,
                            "source_label": doc_title.lower(),
                            "target_label": cache_key,
                            "edge_type": "contains_entity",
                        })

                    # Create concept nodes
                    for concept in extraction.get("concepts", []):
                        label = concept.get("label", "").strip()
                        if not label:
                            continue

                        cache_key = label.lower()
                        if cache_key not in node_cache:
                            node = GraphNode(
                                user_id=user_id,
                                node_type="concept",
                                label=label,
                                description=concept.get("description"),
                                document_id=doc_id,
                            )
                            db.add(node)
                            node_cache[cache_key] = node
                            nodes_created += 1

                        pending_edges.append({
                            "user_id": user_id,
                            "source_label": doc_title.lower(),
                            "target_label": cache_key,
                            "edge_type": "contains_entity",
                        })

                    # Queue relationship edges
                    for rel in extraction.get("relationships", []):
                        source_label = rel.get("source", "").strip().lower()
                        target_label = rel.get("target", "").strip().lower()
                        rel_type = rel.get("type", "related_to")
                        if source_label and target_label:
                            pending_edges.append({
                                "user_id": user_id,
                                "source_label": source_label,
                                "target_label": target_label,
                                "edge_type": rel_type,
                                "description": rel.get("description"),
                            })

                # Single flush to get all node IDs
                await db.flush()

                # Build label → node ID index from flushed nodes
                label_to_id: dict[str, int] = {}
                for label, node in node_cache.items():
                    label_to_id[label] = node.id
                # Use doc_node_cache instead of scanning db.new
                for label, node in doc_node_cache.items():
                    label_to_id[label] = node.id

                # Create edges in batch
                for edge_data in pending_edges:
                    src_id = label_to_id.get(edge_data["source_label"])
                    tgt_id = label_to_id.get(edge_data["target_label"])
                    if src_id and tgt_id:
                        db.add(GraphEdge(
                            user_id=edge_data["user_id"],
                            source_id=src_id,
                            target_id=tgt_id,
                            edge_type=edge_data["edge_type"],
                            description=edge_data.get("description"),
                        ))
                        edges_created += 1

                await db.commit()

            _update_progress(user_id, status="complete", current=total, total=total,
                             failed_count=failed_count, nodes_created=nodes_created, edges_created=edges_created)
            logger.info("Graph build complete for user %d: %d nodes, %d edges, %d failed",
                        user_id, nodes_created, edges_created, failed_count)

        except Exception as e:
            logger.error("Graph build failed for user %d: %s", user_id, e, exc_info=True)
            _update_progress(user_id, status="error", error=str(e)[:200], current=0, total=0)
        finally:
            # Schedule cleanup of progress data after 10 minutes
            async def _cleanup():
                await asyncio.sleep(600)
                _build_progress.pop(user_id, None)
                _build_locks.pop(user_id, None)
            asyncio.create_task(_cleanup())


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


@router.get("/build/status")
async def build_status(current_user: User = Depends(get_current_user_dep)):
    """Get current graph build progress."""
    progress = _build_progress.get(current_user.id, {"status": "idle", "current": 0, "total": 0})
    return progress


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

    # Edges to create after node IDs are flushed
    pending_edges: list[dict] = []

    # Collect all entity and concept labels for batch existence check
    entity_labels = [
        entity.get("label", "").strip()
        for entity in extraction.get("entities", [])
        if entity.get("label", "").strip()
    ]
    concept_labels = [
        concept.get("label", "").strip()
        for concept in extraction.get("concepts", [])
        if concept.get("label", "").strip()
    ]

    # Batch check existing entity nodes to avoid N+1
    if entity_labels:
        existing_entities_result = await db.execute(
            select(GraphNode).where(
                GraphNode.user_id == current_user.id,
                GraphNode.node_type == "entity",
                GraphNode.label.in_(entity_labels),
            )
        )
        existing_entities = {n.label.lower(): n for n in existing_entities_result.scalars().all()}
    else:
        existing_entities = {}

    # Batch check existing concept nodes to avoid N+1
    if concept_labels:
        existing_concepts_result = await db.execute(
            select(GraphNode).where(
                GraphNode.user_id == current_user.id,
                GraphNode.node_type == "concept",
                GraphNode.label.in_(concept_labels),
            )
        )
        existing_concepts = {n.label.lower(): n for n in existing_concepts_result.scalars().all()}
    else:
        existing_concepts = {}

    # Create entity nodes
    new_entity_nodes = []
    for entity in extraction.get("entities", []):
        label = entity.get("label", "").strip()
        if not label:
            continue
        node = existing_entities.get(label.lower())
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
            new_entity_nodes.append(node)

        new_nodes.append(node)

        pending_edges.append({
            "source_id": doc_node.id,
            "target_node": node,
            "edge_type": "contains_entity",
        })

    # Create concept nodes
    new_concept_nodes = []
    for concept in extraction.get("concepts", []):
        label = concept.get("label", "").strip()
        if not label:
            continue
        node = existing_concepts.get(label.lower())
        if not node:
            node = GraphNode(
                user_id=current_user.id,
                node_type="concept",
                label=label,
                description=concept.get("description"),
                document_id=doc.id,
            )
            db.add(node)
            new_concept_nodes.append(node)

        new_nodes.append(node)

        pending_edges.append({
            "source_id": doc_node.id,
            "target_node": node,
            "edge_type": "contains_entity",
        })

    # Single flush for all new nodes to get IDs
    await db.flush()

    # Create edges in batch now that all node IDs are available
    for edge_data in pending_edges:
        db.add(GraphEdge(
            user_id=current_user.id,
            source_id=edge_data["source_id"],
            target_id=edge_data["target_node"].id,
            edge_type=edge_data["edge_type"],
        ))

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


@router.get("/node/{node_id}/documents")
async def get_node_documents(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get all documents that reference a specific graph node (cross-reference)."""
    # Verify the node exists and belongs to the user
    node_result = await db.execute(
        select(GraphNode).where(GraphNode.id == node_id, GraphNode.user_id == current_user.id)
    )
    node = node_result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # If this is a document node, return the document directly
    if node.node_type == "document" and node.document_id:
        doc_result = await db.execute(
            select(Document).where(Document.id == node.document_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            return {"documents": [{"id": doc.id, "title": doc.title, "edge_type": "self"}]}

    # For entity/concept nodes: find all edges where this node is the target
    # (document → entity/concept edges have document node as source, entity as target)
    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.user_id == current_user.id,
            GraphEdge.target_id == node_id,
        )
    )
    edges = edges_result.scalars().all()

    # Get source node IDs (these are document nodes)
    source_node_ids = {e.source_id for e in edges}
    if not source_node_ids:
        return {"documents": []}

    # Batch fetch document nodes
    doc_nodes_result = await db.execute(
        select(GraphNode).where(
            GraphNode.user_id == current_user.id,
            GraphNode.id.in_(source_node_ids),
            GraphNode.node_type == "document",
        )
    )
    doc_nodes = doc_nodes_result.scalars().all()

    # Build edge_type lookup
    edge_type_map = {}
    for e in edges:
        edge_type_map[e.source_id] = e.edge_type

    # Batch fetch actual documents
    doc_ids = {n.document_id for n in doc_nodes if n.document_id}
    if not doc_ids:
        return {"documents": []}

    docs_result = await db.execute(
        select(Document.id, Document.title).where(Document.id.in_(doc_ids))
    )
    docs = {row[0]: row[1] for row in docs_result.all()}

    documents = []
    for dn in doc_nodes:
        if dn.document_id and dn.document_id in docs:
            documents.append({
                "id": dn.document_id,
                "title": docs[dn.document_id],
                "edge_type": edge_type_map.get(dn.id, "related_to"),
            })

    return {"documents": documents}
