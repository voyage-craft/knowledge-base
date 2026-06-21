"""MCP Resources — expose knowledge base data as readable resources."""

from app.mcp.server import mcp
from app.core.database import AsyncSessionLocal
from app.models.document import Document, Tag, Folder, document_tags
from sqlalchemy import select, func


@mcp.resource("kb://documents")
async def list_documents_resource() -> str:
    """List all published documents in the knowledge base."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(Document.status == "published")
            .order_by(Document.updated_at.desc())
            .limit(100)
        )
        docs = result.scalars().all()
        lines = ["# Knowledge Base Documents\n"]
        for doc in docs:
            lines.append(f"- [{doc.title}] (id: {doc.id}, updated: {doc.updated_at.strftime('%Y-%m-%d') if doc.updated_at else 'N/A'})")
        return "\n".join(lines)


@mcp.resource("kb://documents/{document_id}")
async def get_document_resource(document_id: str) -> str:
    """Read a specific document by ID."""
    async with AsyncSessionLocal() as session:
        try:
            doc_id = int(document_id)
        except ValueError:
            return f"Error: Invalid document ID: {document_id}"

        result = await session.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return f"Error: Document {document_id} not found"

        # Get tags
        tag_result = await session.execute(
            select(Tag.name).join(document_tags, Tag.id == document_tags.c.tag_id)
            .where(document_tags.c.document_id == doc_id)
        )
        tags = [row[0] for row in tag_result.fetchall()]

        content = doc.plain_text or "(empty document)"
        tag_str = ", ".join(tags) if tags else "none"
        return f"# {doc.title}\n\nTags: {tag_str}\nStatus: {doc.status}\n\n{content}"


@mcp.resource("kb://folders")
async def list_folders_resource() -> str:
    """List all folders in the knowledge base."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Folder).order_by(Folder.name))
        folders = result.scalars().all()
        if not folders:
            return "# Folders\n\nNo folders created yet."
        lines = ["# Folders\n"]
        for f in folders:
            parent = f" (parent: {f.parent_id})" if f.parent_id else ""
            lines.append(f"- {f.name}{parent} (id: {f.id})")
        return "\n".join(lines)


@mcp.resource("kb://tags")
async def list_tags_resource() -> str:
    """List all tags with document counts."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tag.id, Tag.name, Tag.color, func.count(document_tags.c.document_id).label("count"))
            .outerjoin(document_tags, Tag.id == document_tags.c.tag_id)
            .group_by(Tag.id)
            .order_by(func.count(document_tags.c.document_id).desc())
        )
        rows = result.all()
        if not rows:
            return "# Tags\n\nNo tags created yet."
        lines = ["# Tags\n"]
        for r in rows:
            lines.append(f"- {r[1]} ({r[3]} documents)")
        return "\n".join(lines)


@mcp.resource("kb://stats")
async def get_stats_resource() -> str:
    """Knowledge base statistics overview."""
    async with AsyncSessionLocal() as session:
        doc_count = await session.execute(select(func.count(Document.id)))
        total = doc_count.scalar() or 0

        published = await session.execute(
            select(func.count(Document.id)).where(Document.status == "published")
        )
        pub_count = published.scalar() or 0

        draft = await session.execute(
            select(func.count(Document.id)).where(Document.status == "draft")
        )
        draft_count = draft.scalar() or 0

        folder_count = await session.execute(select(func.count(Folder.id)))
        folders = folder_count.scalar() or 0

        tag_count = await session.execute(select(func.count(Tag.id)))
        tags = tag_count.scalar() or 0

        return (
            f"# Knowledge Base Statistics\n\n"
            f"- Total documents: {total}\n"
            f"- Published: {pub_count}\n"
            f"- Drafts: {draft_count}\n"
            f"- Folders: {folders}\n"
            f"- Tags: {tags}\n"
        )
