"""MCP tool: Knowledge graph exploration."""

from app.mcp.server import mcp
from app.mcp.auth_context import require_user_id
from app.core.database import AsyncSessionLocal
from app.models.graph import GraphNode, GraphEdge
from sqlalchemy import select, or_


@mcp.tool()
async def search_knowledge_graph(query: str, depth: int = 2) -> dict:
    """Search the knowledge graph for entities and relationships matching the query.
    Returns connected nodes and edges up to the specified depth."""
    depth = max(1, min(depth, 4))
    user_id = require_user_id()

    async with AsyncSessionLocal() as session:
        # Find matching nodes (scoped to this user)
        result = await session.execute(
            select(GraphNode).where(
                GraphNode.user_id == user_id,
                or_(
                    GraphNode.label.ilike(f"%{query}%"),
                    GraphNode.entity_type.ilike(f"%{query}%"),
                )
            ).limit(10)
        )
        start_nodes = result.scalars().all()

        if not start_nodes:
            return {"nodes": [], "edges": [], "message": "No matching entities found"}

        # BFS to collect connected nodes up to depth
        visited_nodes = {}
        visited_edges = {}
        current_ids = {n.id for n in start_nodes}

        for n in start_nodes:
            visited_nodes[n.id] = {
                "id": n.id, "name": n.label, "entity_type": n.entity_type,
                "description": n.description or "",
            }

        for _ in range(depth):
            if not current_ids:
                break

            # Find edges connected to current nodes (scoped to this user)
            edge_result = await session.execute(
                select(GraphEdge).where(
                    GraphEdge.user_id == user_id,
                    or_(
                        GraphEdge.source_id.in_(current_ids),
                        GraphEdge.target_id.in_(current_ids),
                    )
                )
            )
            edges = edge_result.scalars().all()

            new_ids = set()
            for edge in edges:
                if edge.id not in visited_edges:
                    visited_edges[edge.id] = {
                        "id": edge.id, "source_id": edge.source_id,
                        "target_id": edge.target_id, "relation": edge.relation,
                    }
                    new_ids.add(edge.source_id)
                    new_ids.add(edge.target_id)

            # Fetch new nodes
            new_ids -= set(visited_nodes.keys())
            if new_ids:
                node_result = await session.execute(
                    select(GraphNode).where(
                        GraphNode.id.in_(new_ids),
                        GraphNode.user_id == user_id,
                    )
                )
                for n in node_result.scalars().all():
                    visited_nodes[n.id] = {
                        "id": n.id, "name": n.label, "entity_type": n.entity_type,
                        "description": n.description or "",
                    }

            current_ids = new_ids

        return {
            "nodes": list(visited_nodes.values()),
            "edges": list(visited_edges.values()),
            "query": query,
        }
