"""MCP tool: List folders and tags."""

from app.mcp.server import mcp
from app.core.database import AsyncSessionLocal
from app.models.document import Folder, Tag, document_tags
from sqlalchemy import select, func


@mcp.tool()
async def list_folders() -> dict:
    """List all folders in the knowledge base."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Folder).order_by(Folder.name))
        folders = result.scalars().all()
        return {
            "folders": [
                {"id": f.id, "name": f.name, "parent_id": f.parent_id}
                for f in folders
            ]
        }


@mcp.tool()
async def list_tags() -> dict:
    """List all tags with document counts."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tag.id, Tag.name, Tag.color, func.count(document_tags.c.document_id).label("count"))
            .outerjoin(document_tags, Tag.id == document_tags.c.tag_id)
            .group_by(Tag.id)
            .order_by(func.count(document_tags.c.document_id).desc())
        )
        rows = result.all()
        return {
            "tags": [
                {"id": r[0], "name": r[1], "color": r[2], "document_count": r[3]}
                for r in rows
            ]
        }
