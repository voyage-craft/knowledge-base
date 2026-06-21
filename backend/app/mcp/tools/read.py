"""MCP tool: Read documents and browse folders/tags."""

from app.mcp.server import mcp
from app.core.database import AsyncSessionLocal
from app.models.document import Document, Tag, document_tags, Folder
from sqlalchemy import select


@mcp.tool()
async def read_document(document_id: int) -> dict:
    """Read a document by ID. Returns title, plain text content, tags, folder, and status."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        tag_result = await session.execute(
            select(Tag.name).join(document_tags, Tag.id == document_tags.c.tag_id)
            .where(document_tags.c.document_id == document_id)
        )
        tags = [row[0] for row in tag_result.fetchall()]

        return {
            "id": doc.id,
            "title": doc.title,
            "content": doc.plain_text or "",
            "status": doc.status,
            "folder_id": doc.folder_id,
            "version": doc.version,
            "tags": tags,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }


@mcp.tool()
async def list_documents(
    folder_id: int | None = None,
    tag_name: str | None = None,
    status: str = "published",
    limit: int = 20,
) -> dict:
    """List documents with optional filters. Returns document summaries."""
    limit = max(1, min(limit, 100))

    async with AsyncSessionLocal() as session:
        query = select(Document).distinct()
        if folder_id is not None:
            query = query.where(Document.folder_id == folder_id)
        if status:
            query = query.where(Document.status == status)
        if tag_name:
            query = query.join(document_tags, Document.id == document_tags.c.document_id)
            query = query.join(Tag, Tag.id == document_tags.c.tag_id)
            query = query.where(Tag.name == tag_name)

        query = query.order_by(Document.updated_at.desc()).limit(limit)
        result = await session.execute(query)
        docs = result.scalars().all()

        return {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "status": doc.status,
                    "folder_id": doc.folder_id,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                }
                for doc in docs
            ],
            "count": len(docs),
        }


@mcp.tool()
async def get_document_versions(document_id: int) -> dict:
    """List version history of a document."""
    from app.models.document import DocumentVersion

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        versions = result.scalars().all()

        return {
            "document_id": document_id,
            "versions": [
                {
                    "version": v.version_number,
                    "title": v.title,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
        }


@mcp.tool()
async def get_folder_tree() -> dict:
    """Get hierarchical folder structure as a tree."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Folder).order_by(Folder.name))
        folders = result.scalars().all()

        # Build tree
        folder_map = {}
        roots = []
        for f in folders:
            node = {"id": f.id, "name": f.name, "parent_id": f.parent_id, "children": []}
            folder_map[f.id] = node

        for f in folders:
            node = folder_map[f.id]
            if f.parent_id and f.parent_id in folder_map:
                folder_map[f.parent_id]["children"].append(node)
            else:
                roots.append(node)

        # Count documents per folder
        from sqlalchemy import func
        doc_counts = await session.execute(
            select(Document.folder_id, func.count(Document.id))
            .where(Document.folder_id.isnot(None))
            .group_by(Document.folder_id)
        )
        counts = {row[0]: row[1] for row in doc_counts.fetchall()}

        def add_counts(node):
            node["document_count"] = counts.get(node["id"], 0)
            for child in node["children"]:
                add_counts(child)

        for root in roots:
            add_counts(root)

        return {"folders": roots}
